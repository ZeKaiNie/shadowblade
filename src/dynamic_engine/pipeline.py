"""
动态审计引擎 - 主流水线

白话讲解：
- 把"布蜜罐 → 进沙箱跑 → 监控研判"三步串起来，对外只暴露一个函数。
- 输入是从 SKILL.md 里解析出的代码块，输出是 DynamicAuditResult。
- 设计上和静态流水线（static_engine/pipeline.py）对齐：可关、可降级、可解释。
"""
from __future__ import annotations

from src.dynamic_engine.honeypot import Honeypot, build_honeypot
from src.dynamic_engine.models import DynamicAuditResult
from src.dynamic_engine.monitor import analyze
from src.dynamic_engine.sandbox import run_in_sandbox


def _select_python_code(
    code_blocks: list[str],
    code_languages: list[str] | None,
) -> str:
    """
    从代码块里挑出要送进沙箱执行的 Python 代码

    白话讲解：
    - 动态引擎当前只执行 Python 代码块（最常见的技能载体）
    - 有语言标记就优先取 python/py/unknown 的块；没有标记就全拼起来
    - 多个块拼接执行，模拟技能被整体运行
    """
    if not code_blocks:
        return ""
    if code_languages and len(code_languages) == len(code_blocks):
        selected = [
            c for c, lang in zip(code_blocks, code_languages)
            if lang.lower() in ("python", "py", "unknown", "")
        ]
        if selected:
            return "\n\n".join(selected)
    return "\n\n".join(code_blocks)


def audit_dynamic(
    code_blocks: list[str],
    code_languages: list[str] | None = None,
    honeypot: Honeypot | None = None,
    backend: str = "auto",
    image: str = "python:3.11-slim",
    timeout: int = 60,
    allow_unsafe_subprocess: bool = False,
    suspicious_targets: list[str] | None = None,
) -> DynamicAuditResult:
    """
    动态审计主入口：在带蜜罐的隔离沙箱里执行技能代码并研判

    参数:
        code_blocks: 从 SKILL.md 提取的代码块
        code_languages: 各代码块的语言标记（可选）
        honeypot: 蜜罐配置，不传则自动生成
        backend: auto / docker / subprocess（见 sandbox.run_in_sandbox）
        image: Docker 镜像
        timeout: 单次执行超时（秒）
        allow_unsafe_subprocess: 是否允许无隔离子进程兜底（默认否）
        suspicious_targets: 恶意域名/IP 列表（不传用默认 IOC）

    返回:
        DynamicAuditResult
    """
    code = _select_python_code(code_blocks, code_languages)
    if not code.strip():
        result = DynamicAuditResult(executed=False, reason="无可执行的 Python 代码块")
        return analyze_empty(result)

    honeypot = honeypot or build_honeypot()
    run_result = run_in_sandbox(
        code,
        honeypot=honeypot,
        backend=backend,
        image=image,
        timeout=timeout,
        allow_unsafe_subprocess=allow_unsafe_subprocess,
    )
    return analyze(run_result, suspicious_targets=suspicious_targets)


def analyze_empty(result: DynamicAuditResult) -> DynamicAuditResult:
    """无代码可跑时的占位结论（不算风险，交上层降级）"""
    from src.dynamic_engine.models import DynamicFinding
    result.findings.append(DynamicFinding("low", result.reason or "无可执行代码"))
    return result
