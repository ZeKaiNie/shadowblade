"""
动态审计引擎 - 隔离沙箱执行器

白话讲解：
- 直接在自己机器上跑陌生技能代码 = 引狼入室。所以我们把它关进"笼子"里跑。
- 首选笼子：Docker 容器（--network none 断网、限内存/CPU、跑完即焚），
  技能就算是恶意的也伤不到宿主机，还断了它把数据发出去的路。
- 备用笼子：受限子进程（**不隔离，仅供本地可信样本测试用**，默认关闭）。
- 两种后端都调用同一个探针 harness.py，拿回统一格式的"行为清单"。

设计原则（对齐静态引擎 scanner.py）：
1. 韧性：Docker 不可用/拉镜像失败 → 返回 executed=False，交上层降级，不抛异常拖垮流程
2. 可控：backend 可选 auto/docker/subprocess；子进程后端必须显式开启
3. 干净：每次执行用独立临时工作区，跑完清理
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.dynamic_engine.harness import _SENTINEL_BEGIN, _SENTINEL_END
from src.dynamic_engine.honeypot import Honeypot, build_honeypot, deploy_files
from src.dynamic_engine.models import BehaviorEvent, SandboxRunResult

_HARNESS_SRC = Path(__file__).with_name("harness.py")
DEFAULT_IMAGE = "python:3.11-slim"


def is_docker_available() -> bool:
    """
    检测 Docker 守护进程是否可用

    白话讲解：能连上 docker daemon 才用得了 Docker 沙箱，
    连不上（没装/没启动/没权限）就返回 False，让上层走降级
    """
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    except Exception:
        return False


def parse_harness_output(stdout: str) -> tuple[list[BehaviorEvent], list[str]]:
    """
    从 harness 的 stdout 里提取行为清单 JSON

    白话讲解：harness 把结果夹在两行哨兵之间输出，
    这里把中间那段 JSON 抠出来解析成 BehaviorEvent 列表
    """
    if _SENTINEL_BEGIN not in stdout or _SENTINEL_END not in stdout:
        return [], []
    block = stdout.split(_SENTINEL_BEGIN, 1)[1].split(_SENTINEL_END, 1)[0].strip()
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        return [], []
    events = [BehaviorEvent.from_dict(e) for e in data.get("events", [])]
    identity = list(data.get("identity_files_written", []))
    return events, identity


def _prepare_workspace(code: str, honeypot: Honeypot) -> tuple[Path, Path]:
    """
    准备一次性工作区：拷贝探针、写入技能代码 + 蜜罐配置 + 布置假文件

    返回: (workspace_dir, config_path)
    """
    workspace = Path(tempfile.mkdtemp(prefix="shadowblade_sbx_"))
    shutil.copy(_HARNESS_SRC, workspace / "harness.py")
    (workspace / "skill_payload.py").write_text(code, encoding="utf-8")
    deploy_files(honeypot, workspace)

    config = {
        "markers": honeypot.markers,
        "env_vars": honeypot.env_vars,
        # 容器内工作区固定挂载到 /work；子进程后端下 cwd 即 workspace
        "payload_path": "skill_payload.py",
    }
    config_path = workspace / "config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return workspace, config_path


def _run_docker(
    workspace: Path,
    image: str,
    timeout: int,
    memory_limit: str,
    cpu_limit: float,
) -> SandboxRunResult:
    """在 Docker 容器里跑探针（断网、限资源、跑完即焚）"""
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",                 # 断网：恶意代码发不出数据
        "--memory", memory_limit,
        "--cpus", str(cpu_limit),
        "--pids-limit", "128",
        "-e", "HOME=/work",                  # 让 ~/.ssh 等解析到挂载的蜜罐文件
        "-v", f"{workspace}:/work",
        "-w", "/work",
        image,
        "python", "/work/harness.py", "config.json",
    ]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        events, identity = parse_harness_output(out)
        return SandboxRunResult(
            executed=True, backend="docker", events=events, stdout=out,
            timed_out=True, identity_files_written=identity,
            reason=f"容器执行超时 ({timeout}s)",
        )

    if r.returncode != 0 and _SENTINEL_BEGIN not in r.stdout:
        # 容器压根没跑起来（镜像缺失/拉取失败/daemon 异常）
        return SandboxRunResult(
            executed=False, backend="docker", stdout=r.stdout, stderr=r.stderr,
            reason=f"Docker 执行失败(rc={r.returncode}): {r.stderr[:300]}",
        )

    events, identity = parse_harness_output(r.stdout)
    return SandboxRunResult(
        executed=True, backend="docker", events=events,
        stdout=r.stdout, stderr=r.stderr, identity_files_written=identity,
    )


def _run_subprocess(workspace: Path, config_path: Path, timeout: int) -> SandboxRunResult:
    """
    在受限子进程里跑探针（⚠️ 不隔离，仅供本地可信样本测试）

    白话讲解：没有 Docker 时的兜底。它**不能**真正隔离恶意代码，
    只是把 HOME 指到临时工作区、限个超时。生产环境绝不能用它跑真恶意样本。
    """
    import os
    import sys

    env = dict(os.environ)
    env["HOME"] = str(workspace)
    try:
        r = subprocess.run(
            [sys.executable, "harness.py", "config.json"],
            cwd=str(workspace), env=env,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        events, identity = parse_harness_output(out)
        return SandboxRunResult(
            executed=True, backend="subprocess", events=events, stdout=out,
            timed_out=True, identity_files_written=identity,
            reason=f"子进程执行超时 ({timeout}s)",
        )
    events, identity = parse_harness_output(r.stdout)
    return SandboxRunResult(
        executed=bool(_SENTINEL_BEGIN in r.stdout), backend="subprocess",
        events=events, stdout=r.stdout, stderr=r.stderr,
        identity_files_written=identity,
        reason="" if _SENTINEL_BEGIN in r.stdout else "子进程未产出行为清单",
    )


def run_in_sandbox(
    code: str,
    honeypot: Honeypot | None = None,
    backend: str = "auto",
    image: str = DEFAULT_IMAGE,
    timeout: int = 60,
    memory_limit: str = "512m",
    cpu_limit: float = 1.0,
    allow_unsafe_subprocess: bool = False,
) -> SandboxRunResult:
    """
    在隔离沙箱里执行一段技能代码并收集行为（主入口）

    参数:
        code: 要执行的技能代码（Python）
        honeypot: 蜜罐配置，不传则自动生成一份
        backend: auto（有 Docker 用 Docker，否则看是否允许子进程）
                 / docker（强制 Docker）/ subprocess（强制子进程，需 allow_unsafe_subprocess）
        image: Docker 镜像
        timeout: 单次执行超时（秒）
        memory_limit / cpu_limit: 容器资源上限
        allow_unsafe_subprocess: 是否允许无隔离的子进程兜底（默认否）

    返回:
        SandboxRunResult；executed=False 时 reason 说明为何没跑
    """
    honeypot = honeypot or build_honeypot()
    workspace, config_path = _prepare_workspace(code, honeypot)

    try:
        use_docker = backend == "docker" or (backend == "auto" and is_docker_available())
        if use_docker:
            return _run_docker(workspace, image, timeout, memory_limit, cpu_limit)

        if backend == "subprocess" or (backend == "auto" and allow_unsafe_subprocess):
            return _run_subprocess(workspace, config_path, timeout)

        return SandboxRunResult(
            executed=False, backend="none",
            reason="Docker 不可用，且未允许子进程兜底（allow_unsafe_subprocess=False）",
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
