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


def _stringify(value, limit: int = 300) -> str:
    """把任意审计参数安全地转成短字符串（截断，避免超长/异常）"""
    try:
        s = str(value)
    except Exception:
        s = "<unstringable>"
    return s[:limit]


def _is_write_mode(args) -> bool:
    """判断一次 open 是否是写入模式（mode 含 w/a/x/+）"""
    for a in args:
        if isinstance(a, str) and any(c in a for c in ("w", "a", "x", "+")):
            return True
    return False


def main() -> int:
    config_path = sys.argv[1]
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    markers = list(config.get("markers", []))
    env_vars = dict(config.get("env_vars", {}))
    payload_path = config["payload_path"]

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
        # 过滤探针自身脚手架文件的读写（框架噪声）
        if behavior in ("file_open", "file_write") and arg_list:
            base = os.path.basename(_stringify(arg_list[0]))
            if base in _OWN_FILES:
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

    sys.addaudithook(_audit_hook)

    # 2) 执行目标技能代码（全程开启采集）
    capturing["on"] = True
    try:
        runpy.run_path(payload_path, run_name="__main__")
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
