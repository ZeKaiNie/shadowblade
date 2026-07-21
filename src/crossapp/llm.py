"""cross-app harness 的离线、确定性 mock LLM。"""

from __future__ import annotations

import re
from typing import Protocol

from src.conformance.capabilities import Capability
from src.crossapp.models import AppAction


class LLMBackend(Protocol):
    """良性 App 所需的最小 LLM 后端协议。"""

    def decide(self, user_request: str, context_text: str, app_id: str) -> AppAction:
        """根据用户请求和共享上下文决定动作。"""


class MockInstructionFollowingLLM:
    """
    透明的指令跟随型 mock agent。

    它编码的不是某个攻击样本的答案，而是一条公开规则：扫描 LLM 收到的
    完整扁平上下文，服从其中出现的祈使式 ``send/upload/exfiltrate/call``
    指令，不区分来源 App、role 或可见性。真实模型的 ASR 不在这里伪造，
    而应由下一轮接入真实 API 后的实际运行结果给出。
    """

    _COMMAND_RE = re.compile(
        r"\b(?P<verb>send|upload|exfiltrate|call|invoke|sync)\b"
        r".*?\b(?:to|target|using)\s+"
        r"(?P<target>[a-zA-Z0-9][a-zA-Z0-9._:/-]*)",
        re.IGNORECASE,
    )
    _CAPABILITY_RE = re.compile(
        r"\b(network|file_read|file_write|subprocess|dynamic_code|"
        r"credential_access|identity_write)\b",
        re.IGNORECASE,
    )
    _CONDITIONAL_RE = re.compile(
        r"\bif\s+(?:the\s+)?(?:user\s+)?(?:asks?|requests?)\s+(?:for\s+)?"
        r"(?P<condition>[^,.;]+)",
        re.IGNORECASE,
    )

    def decide(self, user_request: str, context_text: str, app_id: str) -> AppAction:
        """按透明规则从上下文中找出最后一条满足条件的祈使指令。"""

        lines = context_text.splitlines()
        for line in reversed(lines):
            if "[DATA_ONLY]" in line:
                continue
            content = line.split("] ", 1)[-1]
            conditional = self._CONDITIONAL_RE.search(content)
            condition = conditional.group("condition").strip().lower() if conditional else None
            if condition and condition not in user_request.lower():
                continue
            match = self._COMMAND_RE.search(content)
            if match is None:
                continue
            target = match.group("target").rstrip(".,;)")
            capability_match = self._CAPABILITY_RE.search(content)
            capability = (
                Capability(capability_match.group(1).lower())
                if capability_match
                else Capability.NETWORK
            )
            verb = match.group("verb").lower()
            return AppAction(
                app_id=app_id,
                action_type="tool_call",
                tool_name=verb,
                capability=capability,
                target=target,
                intent=content,
            )
        return AppAction(app_id=app_id)
