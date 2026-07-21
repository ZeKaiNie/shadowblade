"""cross-app 共享上下文防御层与可解释裁决。"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from src.crossapp.context import SharedContext
from src.crossapp.models import (
    ContextRole,
    DefenseEntryDecision,
    SharedContextEntry,
)


class DefenseResult(BaseModel):
    """一次防御变换的上下文结果和逐条裁决。"""

    defense_name: str
    transformed_context: SharedContext
    decisions: list[DefenseEntryDecision] = Field(default_factory=list)
    isolated_entries: list[SharedContextEntry] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class Defense(Protocol):
    """对共享上下文执行一次确定性防御变换的协议。"""

    name: str

    def apply(self, context: SharedContext, consumer_app_id: str) -> DefenseResult:
        """返回可供消费方 App 使用的上下文和解释性裁决。"""


def _copy_context(entries: list[SharedContextEntry]) -> SharedContext:
    """复制上下文，避免防御变换修改攻击取证中的原始记录。"""

    copied = SharedContext()
    for entry in entries:
        copied.append(
            content=entry.content,
            source_app_id=entry.source_app_id,
            role=entry.role,
            visible=entry.visible,
            turn=entry.turn,
        )
    return copied


class NoDefense:
    """不做任何变换的 v1 基线。"""

    name = "NoDefense"

    def apply(self, context: SharedContext, consumer_app_id: str) -> DefenseResult:
        decisions = [
            DefenseEntryDecision(
                source_app_id=entry.source_app_id,
                turn=entry.turn,
                action="pass",
                reason="基线不做来源过滤或上下文变换。",
            )
            for entry in context.entries
        ]
        return DefenseResult(
            defense_name=self.name,
            transformed_context=_copy_context(context.entries),
            decisions=decisions,
            reasons=["NoDefense 保留全部共享上下文条目。"],
        )


class AmplificationRemoval:
    """只移除 system 或静默 App 写入，复现原论文临时启发式。"""

    name = "AmplificationRemoval"

    def apply(self, context: SharedContext, consumer_app_id: str) -> DefenseResult:
        kept: list[SharedContextEntry] = []
        isolated: list[SharedContextEntry] = []
        decisions: list[DefenseEntryDecision] = []
        for entry in context.entries:
            amplified = (
                entry.source_app_id != "user"
                and (entry.role == ContextRole.SYSTEM or not entry.visible)
            )
            if amplified:
                isolated.append(entry)
                decisions.append(
                    DefenseEntryDecision(
                        source_app_id=entry.source_app_id,
                        turn=entry.turn,
                        action="isolate",
                        reason=(
                            "仅因 App 条目使用 system role 或静默可见性，"
                            "按临时放大位启发式隔离。"
                        ),
                    )
                )
            else:
                kept.append(entry)
                decisions.append(
                    DefenseEntryDecision(
                        source_app_id=entry.source_app_id,
                        turn=entry.turn,
                        action="pass",
                        reason="普通可见 app 条目不属于本启发式的放大位。",
                    )
                )
        return DefenseResult(
            defense_name=self.name,
            transformed_context=_copy_context(kept),
            decisions=decisions,
            isolated_entries=isolated,
            reasons=[
                "只中和 system role 和 hidden 条目，保留普通可见跨 App 指令。"
            ],
        )


class Spotlighting:
    """给所有条目增加来源标签，但不删除内容或改变执行通道。"""

    name = "Spotlighting"

    def apply(self, context: SharedContext, consumer_app_id: str) -> DefenseResult:
        transformed: list[SharedContextEntry] = []
        decisions: list[DefenseEntryDecision] = []
        for entry in context.entries:
            labeled = (
                f"[SPOTLIGHT source={entry.source_app_id} role={entry.role.value} "
                f"visible={str(entry.visible).lower()} DATA] {entry.content}"
            )
            transformed.append(entry.model_copy(update={"content": labeled}))
            decisions.append(
                DefenseEntryDecision(
                    source_app_id=entry.source_app_id,
                    turn=entry.turn,
                    action="spotlight",
                    reason="保留原文，仅添加来源、角色和可见性标签。",
                )
            )
        return DefenseResult(
            defense_name=self.name,
            transformed_context=_copy_context(transformed),
            decisions=decisions,
            reasons=["Spotlighting 依赖模型自觉尊重标签，不隔离任何条目。"],
        )


class ProvenanceScopedAuthorization:
    """只允许用户或消费方 App 的指令进入可执行通道。"""

    name = "ProvenanceScopedAuthorization"

    def apply(self, context: SharedContext, consumer_app_id: str) -> DefenseResult:
        transformed: list[SharedContextEntry] = []
        decisions: list[DefenseEntryDecision] = []
        for entry in context.entries:
            trusted = entry.source_app_id in {"user", consumer_app_id}
            if trusted:
                transformed.append(entry.model_copy())
                decisions.append(
                    DefenseEntryDecision(
                        source_app_id=entry.source_app_id,
                        turn=entry.turn,
                        action="pass",
                        reason="来源是用户或消费方 App，允许进入指令通道。",
                    )
                )
                continue

            inert_content = (
                f"[DATA_ONLY] source={entry.source_app_id} role={entry.role.value} "
                f"visible={str(entry.visible).lower()} {entry.content}"
            )
            transformed.append(entry.model_copy(update={"content": inert_content}))
            decisions.append(
                DefenseEntryDecision(
                    source_app_id=entry.source_app_id,
                    turn=entry.turn,
                    action="data_only",
                    reason=(
                        "其它 App 的内容降级为惰性数据，不进入可执行指令通道；"
                        "该裁决不受 role 或 visible 影响。"
                    ),
                )
            )
        return DefenseResult(
            defense_name=self.name,
            transformed_context=_copy_context(transformed),
            decisions=decisions,
            reasons=[
                "仅 user 和消费方 App 的条目可作为指令，其它 App 条目统一降级为数据。"
            ],
        )


DefenseName = Literal[
    "NoDefense",
    "AmplificationRemoval",
    "Spotlighting",
    "ProvenanceScopedAuthorization",
]
