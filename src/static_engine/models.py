"""
SKILL.md 数据模型
定义一个"技能"被解析后的结构化表示

白话讲解：
- SKILL.md 是 OpenClaw 生态里每个技能的说明文件（类似 README）
- 我们需要把它从纯文本变成结构化数据，才能做后续分析
- 比如提取出"这个技能要什么权限""代码在哪""描述了什么功能"
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """风险等级枚举"""
    CRITICAL = "critical"   # 严重：确认恶意
    HIGH = "high"           # 高危：极大概率恶意
    MEDIUM = "medium"       # 中危：可疑，需人工确认
    LOW = "low"             # 低危：轻微异常
    SAFE = "safe"           # 安全：未发现问题


class SkillMetadata(BaseModel):
    """
    从 SKILL.md 中解析出的技能元数据

    白话讲解：这就像一个技能的"身份证"，把散落在 Markdown 里的信息
    提取成一个个字段，方便后续代码直接用。
    """
    # 基本信息
    name: str = Field(default="", description="技能名称")
    description: str = Field(default="", description="技能功能描述")
    author: str = Field(default="", description="作者")
    version: str = Field(default="", description="版本号")

    # 权限相关（S6 权限审计的核心输入）
    declared_capabilities: list[str] = Field(
        default_factory=list,
        description="技能声明的权限列表，如 network_access, file_system_write"
    )
    prerequisites: str = Field(
        default="",
        description="prerequisites 段落原文（ClawHavoc 主要攻击入口）"
    )

    # 代码相关
    code_blocks: list[str] = Field(
        default_factory=list,
        description="从 SKILL.md 提取的所有代码块"
    )
    code_language: list[str] = Field(
        default_factory=list,
        description="每个代码块的语言标记（python/bash/yaml等）"
    )
    entry_file: str = Field(
        default="",
        description="技能入口文件路径（通常在 SKILL.md 里有说明）"
    )

    # 原始内容
    raw_content: str = Field(default="", description="SKILL.md 原始全文")
    char_count: int = Field(default=0, description="原始文本字符数")

    # 安全扫描标记
    has_suspicious_patterns: bool = Field(
        default=False,
        description="是否包含可疑关键词（curl/wget/eval等）"
    )
    matched_patterns: list[str] = Field(
        default_factory=list,
        description="匹配到的可疑关键词列表"
    )
    has_ascii_smuggling: bool = Field(
        default=False,
        description="是否检测到不可见 Unicode 字符隐写"
    )


class SkillAuditResult(BaseModel):
    """
    单个技能的完整审计结果

    白话讲解：这是最终输出——把静态扫描、动态沙箱、AI研判的结果
    汇总到一个结构体里，最后展示给用户看。
    """
    skill_name: str = Field(description="技能名称")
    risk_level: RiskLevel = Field(default=RiskLevel.SAFE, description="综合风险等级")
    trust_score: float = Field(
        default=1.0,
        ge=0.0, le=1.0,
        description="信任评分 0-1，越高越安全"
    )
    risk_score: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="风险评分 0-1，越高越危险（= 1 - trust_score）"
    )

    # 各引擎的发现
    static_findings: list[str] = Field(default_factory=list, description="静态扫描发现")
    dynamic_findings: list[str] = Field(default_factory=list, description="动态沙箱发现")
    ai_findings: list[str] = Field(default_factory=list, description="AI研判发现")

    # 各引擎单独的风险评分（0-1，越高越危险）
    # 白话讲解：分项评分让用户能看到"哪个引擎发现了问题"
    # 比如静态 0.9 但 LLM 0.2 → 可能是规则误报，看 LLM 怎么判断
    static_risk: float = Field(default=0.0, ge=0.0, le=1.0, description="静态扫描风险分")
    dynamic_risk: float = Field(default=0.0, ge=0.0, le=1.0, description="动态沙箱风险分")
    ai_risk: float = Field(default=0.0, ge=0.0, le=1.0, description="AI 研判风险分")

    # 引擎可用性（哪些引擎实际跑了）
    # 白话讲解：M2 阶段没有动态引擎，dynamic_enabled=False，权重会自动重新分配
    static_enabled: bool = Field(default=True, description="静态引擎是否启用")
    dynamic_enabled: bool = Field(default=False, description="动态引擎是否启用")
    ai_enabled: bool = Field(default=False, description="AI 研判是否启用")

    # 权限对比结果
    declared_capabilities: list[str] = Field(default_factory=list, description="声明的权限")
    actual_capabilities: list[str] = Field(default_factory=list, description="实际检测到的权限")
    permission_mismatch: bool = Field(
        default=False,
        description="声明权限与实际行为是否不匹配"
    )

    # 解析阶段标记（来自 SkillMetadata，方便前端直接展示）
    has_suspicious_patterns: bool = Field(default=False, description="是否含可疑关键词")
    matched_patterns: list[str] = Field(default_factory=list, description="匹配到的可疑关键词")
    has_ascii_smuggling: bool = Field(default=False, description="是否含 Unicode 隐写")

    summary: str = Field(default="", description="审计结论摘要（LLM生成或自动生成）")
