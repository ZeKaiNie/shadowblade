"""
声明-观测 一致性核验与风险决策

白话讲解（方向 A 的核心方法）：
1. 声明侧：从 SKILL.md 抽取"技能说自己要哪些能力"→ declared 能力集合。
2. 观测侧：把技能丢进隔离沙箱真跑，看它"实际用了哪些能力"→ observed 能力集合。
3. 类型化比对：
   - undeclared = observed - declared  → "没说却做了"，是偏差(deviation)，重点看敏感能力。
   - unused     = declared - observed  → "说了没做"，一般无害（信息不足），仅记录。
4. 蜜罐取证：若沙箱里的假凭据(canary)被读取/外传(honeypot_triggered)，把"疑似"坐实成"确凿"。
5. 决策：综合未声明敏感能力 + 蜜罐命中 → 放行(allow)/复核(review)/阻断(deny)。

设计原则：
- 决策是确定性的、可解释的（每条 reason 都能说清为什么），不依赖 LLM。
- 分数只用于排序/阈值，真正的硬证据是"蜜罐命中"和"未声明敏感能力"。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.conformance.capabilities import (
    SENSITIVE_CAPABILITIES,
    Capability,
    normalize_declared,
    observed_from_audit,
)
from src.dynamic_engine.models import DynamicAuditResult

# 各未声明敏感能力对偏差分的贡献权重（越危险越高）
_DEVIATION_WEIGHTS: dict[Capability, float] = {
    Capability.IDENTITY_WRITE: 0.5,       # 篡改身份/记忆：控制面攻击，最危险
    Capability.CREDENTIAL_ACCESS: 0.45,   # 私自读凭据
    Capability.NETWORK: 0.35,             # 私自联网（潜在外传通道）
    Capability.DYNAMIC_CODE: 0.3,         # 私自动态执行代码
    Capability.SUBPROCESS: 0.25,          # 私自起子进程
    Capability.FILE_WRITE: 0.15,          # 私自写文件（相对温和）
}

# 决策阈值
_DENY_THRESHOLD = 0.6
_REVIEW_THRESHOLD = 0.25


class ConformanceResult(BaseModel):
    """一致性核验结果（可直接进审计报告）"""
    declared: list[str] = Field(description="声明能力（排序后的字符串）")
    observed: list[str] = Field(description="观测能力（排序后的字符串）")
    undeclared: list[str] = Field(description="未声明却观测到的能力（偏差）")
    unused: list[str] = Field(description="声明了但未观测到的能力")
    undeclared_sensitive: list[str] = Field(description="未声明且属敏感的能力")
    honeypot_triggered: bool = Field(default=False, description="蜜罐是否命中")
    deviation_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="偏差风险分 0-1"
    )
    decision: str = Field(description="决策：allow / review / deny")
    reasons: list[str] = Field(default_factory=list, description="可解释理由")


def _cap_names(caps: set[Capability]) -> list[str]:
    """能力集合 → 排序后的字符串列表（稳定输出，方便测试和展示）。"""
    return sorted(c.value for c in caps)


def verify_conformance(
    declared_capabilities: list[str],
    dynamic_result: DynamicAuditResult,
) -> ConformanceResult:
    """
    执行一致性核验，产出偏差 + 决策。

    参数：
    - declared_capabilities: SKILL.md 抽取的声明权限字符串
      （即 static_engine 的 declared_capabilities 字段）
    - dynamic_result: 动态引擎在隔离沙箱跑出的观测结果

    白话讲解：这是把"声明"和"观测"两条线汇合、做减法、下判断的地方。
    """
    return verify_conformance_caps(
        normalize_declared(declared_capabilities), dynamic_result
    )


def verify_conformance_caps(
    declared: set[Capability],
    dynamic_result: DynamicAuditResult,
) -> ConformanceResult:
    """
    一致性核验核心（直接接收已归一化的声明能力集合）。

    白话讲解：与 verify_conformance 相同，只是声明侧已由调用方归一化好
    （例如已合并了 allowed-tools 与正文关键词），避免二次解析。
    """
    observed = observed_from_audit(dynamic_result)

    undeclared = observed - declared
    unused = declared - observed
    undeclared_sensitive = undeclared & SENSITIVE_CAPABILITIES

    reasons: list[str] = []

    # 1) 偏差分：未声明敏感能力累加权重
    score = 0.0
    for capability in undeclared_sensitive:
        weight = _DEVIATION_WEIGHTS.get(capability, 0.1)
        score += weight
        reasons.append(f"未声明却使用了敏感能力：{capability.value}（+{weight:.2f}）")

    # 2) 蜜罐命中：确凿的凭据窃取证据，强力加分
    honeypot = dynamic_result.honeypot_triggered
    if honeypot:
        score += 0.6
        reasons.append("蜜罐命中：假凭据(canary)被读取/外传，确认存在凭据窃取行为（+0.60）")

    # 3) 组合升级：未声明联网 + 蜜罐命中 = 典型"读凭据→外传"链条
    if honeypot and Capability.NETWORK in undeclared:
        score += 0.15
        reasons.append("组合证据：未声明联网 + 蜜罐命中 → 疑似凭据外传链条（+0.15）")

    score = min(score, 1.0)

    # 4) 决策
    if score >= _DENY_THRESHOLD or honeypot:
        decision = "deny"
    elif score >= _REVIEW_THRESHOLD:
        decision = "review"
    else:
        decision = "allow"

    if not reasons:
        reasons.append("未发现未声明的敏感行为，声明与观测基本一致")

    return ConformanceResult(
        declared=_cap_names(declared),
        observed=_cap_names(observed),
        undeclared=_cap_names(undeclared),
        unused=_cap_names(unused),
        undeclared_sensitive=_cap_names(undeclared_sensitive),
        honeypot_triggered=honeypot,
        deviation_score=score,
        decision=decision,
        reasons=reasons,
    )
