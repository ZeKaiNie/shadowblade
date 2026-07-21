"""cross-app 上下文投毒复现 harness 的数据模型。"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.conformance.capabilities import Capability


class ContextRole(str, Enum):
    """共享上下文中条目的来源角色。"""

    USER = "user"
    APP = "app"
    SYSTEM = "system"


class PayloadStyle(str, Enum):
    """论文攻击中两种常见的投毒指令风格。"""

    CONDITIONAL = "conditional"
    IMPERATIVE = "imperative"


class SharedContextEntry(BaseModel):
    """一条扁平共享上下文记录，保留攻击取证所需的来源信息。"""

    content: str
    source_app_id: str
    role: ContextRole
    visible: bool = True
    turn: int = Field(ge=1)


class AppAction(BaseModel):
    """App 或 LLM 决定执行的动作。"""

    app_id: str
    action_type: Literal["none", "tool_call"] = "none"
    tool_name: str | None = None
    capability: Capability | None = None
    target: str | None = None
    intent: str | None = None

    @property
    def is_noop(self) -> bool:
        """判断动作是否表示不调用工具。"""

        return self.action_type == "none"


class AttackerIntent(BaseModel):
    """恶意 App 写入上下文、希望良性 App 执行的攻击意图。"""

    target: str
    capability: Capability
    tool_name: str
    description: str


class AttackEvidence(BaseModel):
    """解释攻击成功或失败时使用的上下文证据。"""

    context_entry: SharedContextEntry | None = None
    matched: bool = False
    explanation: str


class DefenseEntryDecision(BaseModel):
    """防御对单条上下文记录的确定性裁决。"""

    source_app_id: str
    turn: int
    action: Literal["pass", "isolate", "spotlight", "data_only"]
    capability: Capability | None = None
    reason: str


class CrossAppSessionResult(BaseModel):
    """一次恶意 App→良性 App 会话的结构化复现结果。"""

    attack_succeeded: bool
    benign_action: AppAction
    attacker_intent: AttackerIntent | None = None
    evidence: AttackEvidence
    reasons: list[str] = Field(default_factory=list)
