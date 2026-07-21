"""cross-app 上下文投毒复现 harness v1。"""

from src.crossapp.apps import App, BenignApp, MaliciousApp
from src.crossapp.context import FirstPartyAPI, SharedContext
from src.crossapp.llm import LLMBackend, MockInstructionFollowingLLM
from src.crossapp.models import (
    AppAction,
    AttackerIntent,
    AttackEvidence,
    ContextRole,
    CrossAppSessionResult,
    PayloadStyle,
    SharedContextEntry,
)
from src.crossapp.session import CrossAppSession

__all__ = [
    "App",
    "AppAction",
    "AttackEvidence",
    "AttackerIntent",
    "BenignApp",
    "ContextRole",
    "CrossAppSession",
    "CrossAppSessionResult",
    "FirstPartyAPI",
    "LLMBackend",
    "MaliciousApp",
    "MockInstructionFollowingLLM",
    "PayloadStyle",
    "SharedContext",
    "SharedContextEntry",
]
