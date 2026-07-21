"""混合级联检测器：用运行时确认层确认或剪枝静态告警。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from src.conformance.pipeline import SkillConformanceReport, verify_skill_from_code
from src.dynamic_engine.honeypot import Honeypot
from src.static_engine.pipeline import audit_skill


class CascadeResult(BaseModel):
    """级联检测的一次完整结果。"""

    stage1_risk: float = Field(ge=0.0, le=1.0, description="静态扫描风险分")
    stage1_flag: bool = Field(description="静态扫描是否达到候选阈值")
    stage2_ran: bool = Field(description="是否触发运行时确认层")
    stage2_executed: bool = Field(description="运行时沙箱是否真的执行")
    stage2_decision: str | None = Field(default=None, description="运行时决策")
    stage2_deviation: float | None = Field(default=None, description="运行时偏差分")
    honeypot_triggered: bool = Field(description="蜜罐是否命中")
    final_decision: str = Field(description="最终决策：allow/review/deny")
    final_flag: bool = Field(description="最终是否标记为可疑")
    stage2_outcome: str = Field(
        description="skipped/confirmed/refuted/abstained/always_run"
    )
    reasons: list[str] = Field(default_factory=list, description="中文可解释理由")


def _append_code_blocks(
    skill_md_text: str,
    code_blocks: list[str],
    code_languages: list[str] | None,
) -> str:
    """把独立脚本包装成 Markdown 代码块，喂给只解析 Markdown 的静态引擎。"""

    chunks = [skill_md_text.rstrip()]
    for index, code in enumerate(code_blocks):
        language = (
            code_languages[index]
            if code_languages is not None and index < len(code_languages)
            else "python"
        )
        chunks.append(f"```{language or 'python'}\n{code}\n```")
    return "\n\n".join(chunks)


def _default_stage1(markdown: str) -> Any:
    """默认的 Stage-1 调用；关闭 LLM 和动态执行，保持候选层轻量。"""

    return audit_skill(
        markdown,
        enable_static_scan=True,
        enable_llm=False,
        enable_dynamic=False,
    )


def _default_stage2(
    skill_md_text: str,
    code_blocks: list[str],
    code_languages: list[str] | None,
    honeypot: Honeypot | None,
    backend: str,
    timeout: int,
) -> SkillConformanceReport:
    """默认的 Stage-2 调用，未知代码仍由 conformance 管线负责隔离执行。"""

    return verify_skill_from_code(
        skill_md_text=skill_md_text,
        code_blocks=code_blocks,
        code_languages=code_languages,
        honeypot=honeypot,
        backend=backend,
        timeout=timeout,
    )


def run_cascade(
    skill_md_text: str,
    code_blocks: list[str],
    code_languages: list[str] | None = None,
    stage1_threshold: float = 0.2,
    backend: str = "docker",
    timeout: int = 20,
    honeypot: Honeypot | None = None,
    gate: bool = True,
    stage1_fn: Callable[[str], Any] | None = None,
    stage2_fn: Callable[..., Any] | None = None,
) -> CascadeResult:
    """
    运行两级级联，并严格区分 confirmed/refuted/abstained 三种结果。

    ``gate=True`` 保持原来的静态门控行为；``gate=False`` 时所有样本都执行
    Stage-2，最终决策直接采用运行时结论。``stage1_fn`` 和 ``stage2_fn``
    是测试注入点；不传时使用项目已有管线。
    """

    if not 0.0 <= stage1_threshold <= 1.0:
        raise ValueError("stage1_threshold 必须在 0 到 1 之间")

    static_markdown = _append_code_blocks(skill_md_text, code_blocks, code_languages)
    stage1_report = (stage1_fn or _default_stage1)(static_markdown)
    stage1_risk = float(stage1_report.risk_score)
    stage1_flag = stage1_risk >= stage1_threshold
    reasons = [
        f"Stage-1 静态风险分为 {stage1_risk:.3f}，阈值为 {stage1_threshold:.3f}。"
    ]

    if gate and not stage1_flag:
        reasons.append("风险分低于候选阈值，跳过 Stage-2 以节省沙箱算力，最终放行。")
        return CascadeResult(
            stage1_risk=stage1_risk,
            stage1_flag=False,
            stage2_ran=False,
            stage2_executed=False,
            honeypot_triggered=False,
            final_decision="allow",
            final_flag=False,
            stage2_outcome="skipped",
            reasons=reasons,
        )

    if gate:
        reasons.append("风险分达到低门槛候选阈值，触发 Stage-2 运行时确认。")
    else:
        reasons.append(
            "当前为非门控模式：所有样本都执行 Stage-2，最终决策直接采用运行时确认结论。"
        )
    report = (
        stage2_fn or _default_stage2
    )(
        skill_md_text=skill_md_text,
        code_blocks=code_blocks,
        code_languages=code_languages,
        honeypot=honeypot,
        backend=backend,
        timeout=timeout,
    )
    stage2_decision = str(report.decision)
    stage2_executed = bool(report.executed)
    conformance = report.conformance
    stage2_deviation = float(conformance.deviation_score)
    honeypot_triggered = bool(conformance.honeypot_triggered)

    if not gate:
        reasons.append(
            f"非门控模式采用 Stage-2 结论={stage2_decision}，执行={stage2_executed}，"
            f"偏差分={stage2_deviation:.3f}，蜜罐命中={honeypot_triggered}。"
        )
        return CascadeResult(
            stage1_risk=stage1_risk,
            stage1_flag=stage1_flag,
            stage2_ran=True,
            stage2_executed=stage2_executed,
            stage2_decision=stage2_decision,
            stage2_deviation=stage2_deviation,
            honeypot_triggered=honeypot_triggered,
            final_decision=stage2_decision,
            final_flag=stage2_decision != "allow",
            stage2_outcome="always_run",
            reasons=reasons,
        )

    if stage2_decision != "allow":
        outcome = "confirmed"
        final_decision = stage2_decision
        reasons.append(
            f"Stage-2 已执行={stage2_executed}，结论为 {stage2_decision}，"
            "观测到运行时偏差/敏感行为，确认 Stage-1 告警。"
        )
    elif stage2_executed:
        outcome = "refuted"
        final_decision = "allow"
        reasons.append(
            "Stage-2 沙箱真实执行且结论为 allow，未观测到偏差，"
            "因此将 Stage-1 告警证伪并剪枝为放行。"
        )
    else:
        outcome = "abstained"
        final_decision = "review"
        reasons.append(
            "Stage-2 未真实执行，无法获得运行时证据，不能据此剪枝，"
            "保留 Stage-1 告警并转人工复核。"
        )

    reasons.append(
        f"Stage-2 结论={stage2_decision}，执行={stage2_executed}，"
        f"偏差分={stage2_deviation:.3f}，蜜罐命中={honeypot_triggered}。"
    )
    return CascadeResult(
        stage1_risk=stage1_risk,
        stage1_flag=True,
        stage2_ran=True,
        stage2_executed=stage2_executed,
        stage2_decision=stage2_decision,
        stage2_deviation=stage2_deviation,
        honeypot_triggered=honeypot_triggered,
        final_decision=final_decision,
        final_flag=final_decision != "allow",
        stage2_outcome=outcome,
        reasons=reasons,
    )
