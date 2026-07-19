"""
方向 A 端到端管线：SKILL.md → 声明抽取 → 沙箱观测 → 一致性核验 → 决策

白话讲解：
- 把已有的三块拼起来跑通一个技能：
    1) 用 static_engine 的解析器抽取"声明能力"；
    2) 用 dynamic_engine 在带蜜罐(canary)的隔离沙箱里真跑代码，得到"观测能力"；
    3) 用 conformance 做类型化比对 + 决策。
- 安全约束：恶意/未知代码必须在 Docker 沙箱里跑（backend='docker'），绝不在宿主执行。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.conformance.conformance import ConformanceResult, verify_conformance
from src.dynamic_engine.honeypot import Honeypot
from src.dynamic_engine.pipeline import audit_dynamic
from src.static_engine.skill_parser import extract_capabilities


class SkillConformanceReport(BaseModel):
    """单个技能的一致性核验报告（方向 A 输出）"""
    declared_capabilities: list[str] = Field(description="SKILL.md 声明的原始权限字符串")
    executed: bool = Field(description="沙箱是否真的执行了代码")
    backend: str = Field(description="执行后端 docker/subprocess/none")
    dynamic_risk: float = Field(description="动态引擎风险分 0-1")
    conformance: ConformanceResult = Field(description="一致性核验结果")

    @property
    def decision(self) -> str:
        """最终决策（allow/review/deny）直接取一致性核验的决策。"""
        return self.conformance.decision


def verify_skill_from_code(
    skill_md_text: str,
    code_blocks: list[str],
    code_languages: list[str] | None = None,
    honeypot: Honeypot | None = None,
    backend: str = "docker",
    image: str = "python:3.11-slim",
    timeout: int = 60,
    allow_unsafe_subprocess: bool = False,
) -> SkillConformanceReport:
    """
    对"SKILL.md 文本 + 代码块"跑完整方向 A 管线。

    参数：
    - skill_md_text: SKILL.md 原始文本（用于抽取声明能力）
    - code_blocks / code_languages: 要在沙箱执行的代码
    - honeypot: 蜜罐配置，不传则动态引擎自动生成随机 canary
    - backend: 默认 'docker'（隔离执行未知代码的安全底线）

    白话讲解：声明侧只看文本、不执行；观测侧进沙箱真跑；最后合流做核验。
    """
    declared = extract_capabilities(skill_md_text)

    dynamic_result = audit_dynamic(
        code_blocks=code_blocks,
        code_languages=code_languages,
        honeypot=honeypot,
        backend=backend,
        image=image,
        timeout=timeout,
        allow_unsafe_subprocess=allow_unsafe_subprocess,
    )

    conformance = verify_conformance(declared, dynamic_result)

    return SkillConformanceReport(
        declared_capabilities=declared,
        executed=dynamic_result.executed,
        backend=dynamic_result.backend,
        dynamic_risk=dynamic_result.risk_score,
        conformance=conformance,
    )
