"""cross-app 上下文投毒复现 harness v1。"""

from src.crossapp.apps import App, BenignApp, MaliciousApp
from src.crossapp.context import FirstPartyAPI, SharedContext
from src.crossapp.defense import (
    AmplificationRemoval,
    Defense,
    DefenseResult,
    NoDefense,
    ProvenanceScopedAuthorization,
    Spotlighting,
)
from src.crossapp.evaluate import (
    CrossAppScenario,
    DefenseEvaluation,
    evaluate_defenses,
    synthetic_scenarios,
)
from src.crossapp.llm import LLMBackend, MockInstructionFollowingLLM
from src.crossapp.models import (
    AppAction,
    AttackerIntent,
    AttackEvidence,
    ContextRole,
    CrossAppSessionResult,
    DefenseEntryDecision,
    PayloadStyle,
    SharedContextEntry,
)
from src.crossapp.session import CrossAppSession

__all__ = [
    "App",
    "AppAction",
    "AmplificationRemoval",
    "AttackEvidence",
    "AttackerIntent",
    "BenignApp",
    "ContextRole",
    "CrossAppSession",
    "CrossAppSessionResult",
    "CrossAppScenario",
    "Defense",
    "DefenseEntryDecision",
    "DefenseEvaluation",
    "DefenseResult",
    "evaluate_defenses",
    "FirstPartyAPI",
    "LLMBackend",
    "MaliciousApp",
    "MockInstructionFollowingLLM",
    "NoDefense",
    "PayloadStyle",
    "ProvenanceScopedAuthorization",
    "Spotlighting",
    "SharedContext",
    "SharedContextEntry",
    "synthetic_scenarios",
]
