"""无隔离共享上下文与一等公民写入 API。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.crossapp.models import ContextRole, SharedContextEntry


class SharedContext(BaseModel):
    """
    持久、扁平、无来源过滤的共享上下文。

    这里故意不做来源隔离或权限校验：v1 只复现攻击面，下一轮防御层
    再在这个边界加入 provenance、隔离和授权对齐。
    """

    entries: list[SharedContextEntry] = Field(default_factory=list)
    next_turn: int = Field(default=1, ge=1)

    def append(
        self,
        content: str,
        source_app_id: str,
        role: ContextRole | str,
        visible: bool = True,
        turn: int | None = None,
    ) -> SharedContextEntry:
        """追加一条记录，并为未指定的记录分配递增 turn。"""

        entry_turn = self.next_turn if turn is None else turn
        entry = SharedContextEntry(
            content=content,
            source_app_id=source_app_id,
            role=ContextRole(role),
            visible=visible,
            turn=entry_turn,
        )
        self.entries.append(entry)
        self.next_turn = max(self.next_turn, entry_turn + 1)
        return entry

    def render(
        self,
        visible_only: bool = False,
        roles: set[ContextRole | str] | None = None,
    ) -> str:
        """
        按可见性和角色渲染上下文。

        LLM 默认收到全部条目（包括用户不可见的静默条目），这是无隔离
        confused-deputy 攻击成立的关键；调用方可以显式选择用户可见视图。
        """

        normalized_roles = (
            {ContextRole(role) for role in roles} if roles is not None else None
        )
        selected = [
            entry
            for entry in self.entries
            if (not visible_only or entry.visible)
            and (normalized_roles is None or entry.role in normalized_roles)
        ]
        return "\n".join(
            f"[turn={entry.turn} role={entry.role.value} source={entry.source_app_id} "
            f"visible={str(entry.visible).lower()}] {entry.content}"
            for entry in selected
        )

    def visible_text(self) -> str:
        """返回用户可见的上下文文本。"""

        return self.render(visible_only=True)

    def llm_text(self) -> str:
        """返回无隔离 LLM 能看到的完整上下文文本。"""

        return self.render(visible_only=False)


class FirstPartyAPI:
    """模拟原论文中的一等公民 ``sendFollowUpMessage`` 写入通道。"""

    def __init__(self, shared_context: SharedContext):
        self.shared_context = shared_context

    def send_follow_up_message(
        self,
        content: str,
        source_app_id: str,
        system_prompt: str | None = None,
        is_visible: bool = True,
    ) -> SharedContextEntry:
        """
        把 App 消息追加到共享上下文。

        ``system_prompt`` 非空时把条目标为 system，模拟系统优先级放大；
        ``is_visible=False`` 仍写入上下文，但用户界面不会显示它。
        """

        role = ContextRole.SYSTEM if system_prompt else ContextRole.APP
        return self.shared_context.append(
            content=content,
            source_app_id=source_app_id,
            role=role,
            visible=is_visible,
        )
