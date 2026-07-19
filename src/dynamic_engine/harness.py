"""
动态审计引擎 - 沙箱内执行探针（harness）

白话讲解：
- 这个脚本是"卧底"，它被放进隔离沙箱（Docker 容器或受限子进程）里运行。
- 它做三件事：
  1. 布置蜜罐现场（注入假环境变量 + 写假凭据文件）
  2. 用 CPython 的审计钩子（sys.addaudithook）盯着技能代码的一举一动
     —— 每次开文件、连网络、起子进程、动态执行代码，都会被记一笔
  3. 跑完后把"行为清单"以 JSON 形式吐出来（夹在特殊标记之间，方便外面提取）

为什么用 sys.addaudithook？
- 这是 Python 3.8+ 官方提供的运行时安全审计接口，能拿到 open/socket.connect/
  subprocess.Popen 等事件的真实参数，比 strace 轻、比猜关键词准。
- 关键点：如果技能读了蜜罐假凭据、又把它塞进网络请求或命令行，
  那段随机标记就会出现在事件参数里 —— 这就是数据外传的铁证。

⚠️ 本脚本只用标准库，保证在 python:slim 这种最小镜像里也能直接跑，无需 pip 安装。
"""
import inspect
import json
import os
import runpy
import socket
import sys
import traceback

# 输出哨兵：外部解析器靠这两行之间的内容提取事件 JSON
_SENTINEL_BEGIN = "<<<SHADOWBLADE_EVENTS_BEGIN>>>"
_SENTINEL_END = "<<<SHADOWBLADE_EVENTS_END>>>"

# 关注的审计事件 → 行为类型 映射
_EVENT_BEHAVIOR = {
    "open": "file_open",
    "os.open": "file_open",
    "socket.connect": "network",
    "socket.getaddrinfo": "network",
    "urllib.Request": "network",
    "http.client.connect": "network",
    "subprocess.Popen": "subprocess",
    "os.system": "subprocess",
    "os.exec": "subprocess",
    "exec": "dynamic_code",
    "compile": "dynamic_code",
}

_IDENTITY_FILE_NAMES = {"SOUL.md", "MEMORY.md", "AGENTS.md"}

# 探针自身的脚手架文件，读写它们属于框架噪声，不计入技能行为
_OWN_FILES = {"harness.py", "skill_payload.py", "config.json"}

# 样本代码文件名（用于判断"哪些函数是样本自己定义的"）
_PAYLOAD_BASENAME = "skill_payload.py"

# 常见入口函数名（优先按此顺序调用；agent 一般会调用这些"入口"来使用技能）
_ENTRYPOINT_PRIORITY = (
    "main", "run", "execute", "start", "handler", "handle", "invoke",
    "entry", "entrypoint", "process", "process_commands", "setup",
    "install", "activate", "init", "app",
)

# 单次执行最多主动调用的入口函数数量（防止极端样本函数过多拖垮沙箱）
_MAX_ENTRYPOINTS = 60


def _no_required_args(func) -> bool:
    """判断一个函数是否可以"无参调用"（所有形参都有默认值或是 *args/**kwargs）。"""
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return False
    for p in sig.parameters.values():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if p.default is p.empty:
            return False
    return True


def _invoke_entrypoints(namespace: dict) -> None:
    """
    顶层执行后，主动调用样本"自己定义、可无参调用"的入口函数。

    白话讲解（为什么需要）：
    - 很多恶意技能把窃密/外传逻辑写在 main()/run()/process_commands() 等函数里，
      指望 agent 在使用技能时去调用；而我们只 `runpy` 跑模块顶层的话，这些函数
      只被"定义"、不会被"执行"，运行时观测就抓不到它们的恶意行为。
    - 这里模拟"agent 调用技能入口"：只调用**样本自己定义**（非 import 进来的库函数）、
      且**无需参数**就能调用的函数，优先常见入口名。全程在隔离沙箱内（断网+限资源）。
    - 单个入口报错不影响其它入口与已采集到的行为。
    """
    funcs: dict[str, object] = {}
    for name, obj in list(namespace.items()):
        if name.startswith("__"):
            continue
        if not inspect.isfunction(obj):
            continue
        code = getattr(obj, "__code__", None)
        # 只调用样本自己定义的函数（co_filename 指向 skill_payload.py），
        # 不去碰 import 进来的第三方/标准库函数，避免误触框架副作用。
        if code is None or not code.co_filename.endswith(_PAYLOAD_BASENAME):
            continue
        if _no_required_args(obj):
            funcs[name] = obj

    # 优先按常见入口名调用，其余样本函数兜底补充
    ordered = [funcs[n] for n in _ENTRYPOINT_PRIORITY if n in funcs]
    ordered += [f for n, f in funcs.items() if n not in _ENTRYPOINT_PRIORITY]

    for func in ordered[:_MAX_ENTRYPOINTS]:
        try:
            func()
        except SystemExit:
            pass
        except BaseException:
            # 入口自身报错不影响探针继续观测其它入口
            pass


def _stringify(value, limit: int = 300) -> str:
    """把任意审计参数安全地转成短字符串（截断，避免超长/异常）"""
    try:
        s = str(value)
    except Exception:
        s = "<unstringable>"
    return s[:limit]


# Python 解释器 / 标准库 / 第三方包的安装位置前缀（import 机制读这些文件属框架噪声）
_FRAMEWORK_PATH_PARTS = (
    "/usr/lib/python",
    "/usr/local/lib/python",
    "site-packages",
    "dist-packages",
    "lib-dynload",
    "/_shims/",
    "<frozen",
)


def _is_framework_path(path: str) -> bool:
    """判断一个文件路径是否属于解释器/库/shim（import 机制读写它们是必要噪声）。"""
    return any(part in path for part in _FRAMEWORK_PATH_PARTS)


def _is_write_mode(args) -> bool:
    """
    判断一次 open 是否是写入模式。

    白话讲解：open 审计事件的参数是 (path, mode, flags)。
    只能看 mode 字符串（第 2 个参数）或 flags 位标志，**绝不能扫 path** ——
    否则像 /work/、download 这种路径里带 'w'/'a'/'x' 会被误判成写入。
    """
    # 优先看 mode 字符串（如 'r' / 'w' / 'a+' / 'rb'）
    if len(args) >= 2 and isinstance(args[1], str):
        return any(c in args[1] for c in ("w", "a", "x", "+"))
    # 退化：看 os.open 的整数 flags 位
    if len(args) >= 3 and isinstance(args[2], int):
        return bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))
    return False


def main() -> int:
    config_path = sys.argv[1]
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    markers = list(config.get("markers", []))
    env_vars = dict(config.get("env_vars", {}))
    payload_path = config["payload_path"]
    # 是否在顶层执行后主动调用样本定义的入口函数（默认开启）
    invoke_entrypoints = bool(config.get("invoke_entrypoints", True))

    events: list[dict] = []
    identity_written: list[str] = []
    # 采集开关：布置现场和收尾时关掉，只在跑技能代码期间开着
    capturing = {"on": False}

    def _audit_hook(event: str, args):
        if not capturing["on"]:
            return
        behavior = _EVENT_BEHAVIOR.get(event)
        if behavior is None:
            return

        arg_list = list(args)
        # 过滤框架/依赖导入产生的文件读写噪声：
        # 1) 探针自身脚手架文件；2) Python 解释器/标准库/site-packages；3) shim 兜底目录。
        # 这些都是"跑起来"的必要机制，不是技能自身的行为。
        if behavior in ("file_open", "file_write") and arg_list:
            path = _stringify(arg_list[0])
            base = os.path.basename(path)
            # 跳过：探针脚手架文件 / 解释器库文件 / 文件描述符(整数)——
            # 文件描述符(如 open(3, 'wb')) 是解释器内部 I/O，不是技能的文件行为。
            if base in _OWN_FILES or _is_framework_path(path) or path.strip().isdigit():
                return

        str_args = [_stringify(a) for a in arg_list]
        joined = " ".join(str_args)
        hits = any(m in joined for m in markers) if markers else False

        # 动态执行代码噪声大（含 runpy 引导），仅当命中蜜罐标记时才记录
        if behavior == "dynamic_code" and not hits:
            return

        # open 的写模式单独归类为 file_write，并记录身份文件篡改
        if event == "open" and _is_write_mode(arg_list):
            behavior = "file_write"
            base = os.path.basename(_stringify(arg_list[0])) if arg_list else ""
            if base in _IDENTITY_FILE_NAMES:
                identity_written.append(_stringify(arg_list[0]))

        events.append(
            {"behavior": behavior, "event": event, "args": str_args, "hits_honeypot": hits}
        )

    # 1) 注入蜜罐环境变量（假凭据，值里带随机标记）
    for k, v in env_vars.items():
        os.environ[k] = v

    # 防止技能里的网络调用长时间阻塞沙箱
    socket.setdefaulttimeout(3)

    # 挂载依赖兜底 shim：把 _shims 目录追加到 sys.path 末尾（不遮蔽真库/标准库），
    # 并安装"缺失依赖自动占位"finder。这样缺 requests 等库的技能也能跑到暴露行为那步。
    shims_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shims")
    if os.path.isdir(shims_dir):
        sys.path.append(shims_dir)
        try:
            import _autostub

            _autostub.install()
        except Exception:
            sys.stderr.write("[harness] autostub 安装失败（忽略）\n")

    sys.addaudithook(_audit_hook)

    # 2) 执行目标技能代码（全程开启采集）
    capturing["on"] = True
    try:
        # 先跑模块顶层；run_path 返回模块的全局命名空间（含其中定义的函数）
        module_ns = runpy.run_path(payload_path, run_name="__main__")
        # 再模拟"agent 调用技能入口"：调用样本自己定义、可无参调用的入口函数，
        # 触发那些藏在函数体里、顶层不会执行的窃密/外传逻辑。
        if invoke_entrypoints and isinstance(module_ns, dict):
            _invoke_entrypoints(module_ns)
    except SystemExit:
        pass
    except BaseException:
        # 技能自身报错不影响我们收集已发生的行为
        sys.stderr.write("[harness] payload raised:\n" + traceback.format_exc())
    finally:
        capturing["on"] = False

    # 3) 输出行为清单
    payload = {
        "events": events,
        "identity_files_written": sorted(set(identity_written)),
    }
    sys.stdout.write("\n" + _SENTINEL_BEGIN + "\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n" + _SENTINEL_END + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
