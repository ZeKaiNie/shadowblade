"""
一致性核验（Conformance）模块

方向 A 的方法核心：把"技能声明的能力"与"运行时真实观测到的能力"做类型化比对，
未声明却出现的敏感行为（deviation）+ 蜜罐取证 → 风险决策（放行/复核/阻断）。
"""
from src.conformance.capabilities import (
    SENSITIVE_CAPABILITIES,
    Capability,
    normalize_declared,
    observed_from_audit,
    observed_from_events,
)
from src.conformance.conformance import (
    ConformanceResult,
    verify_conformance,
)

__all__ = [
    "Capability",
    "SENSITIVE_CAPABILITIES",
    "normalize_declared",
    "observed_from_audit",
    "observed_from_events",
    "ConformanceResult",
    "verify_conformance",
]
