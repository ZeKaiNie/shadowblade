"""
统一能力分类学（Capability Taxonomy）

白话讲解：
- "声明侧"（SKILL.md 里写的权限）和"观测侧"（沙箱里真跑出来的行为）用词五花八门，
  必须先归一到同一套"能力"枚举，才能做类型化比对。
- 这里定义 7 类能力，并提供两个方向的归一化函数：
    normalize_declared()  —— 把声明字符串 → 能力集合
    observed_from_*()     —— 把动态引擎的观测 → 能力集合
"""
from __future__ import annotations

from enum import Enum

from src.dynamic_engine.models import (
    BehaviorEvent,
    BehaviorType,
    DynamicAuditResult,
)


class Capability(str, Enum):
    """统一能力枚举（声明侧与观测侧共用）"""
    NETWORK = "network"                    # 网络访问
    FILE_READ = "file_read"                # 读文件
    FILE_WRITE = "file_write"              # 写文件
    SUBPROCESS = "subprocess"              # 起子进程 / 执行 shell
    DYNAMIC_CODE = "dynamic_code"          # 动态执行代码 eval/exec
    CREDENTIAL_ACCESS = "credential_access"  # 访问凭据/密钥/token
    IDENTITY_WRITE = "identity_write"      # 篡改 agent 身份/记忆文件（控制面攻击）


# 敏感能力：未声明却出现时应重点告警（FILE_READ 相对温和，不列入）
SENSITIVE_CAPABILITIES: frozenset[Capability] = frozenset(
    {
        Capability.NETWORK,
        Capability.SUBPROCESS,
        Capability.DYNAMIC_CODE,
        Capability.CREDENTIAL_ACCESS,
        Capability.IDENTITY_WRITE,
    }
)

# 声明字符串 → 能力 的关键词映射（大小写不敏感，子串匹配）
_DECLARED_KEYWORDS: dict[Capability, tuple[str, ...]] = {
    Capability.NETWORK: (
        "network", "http", "https", "url", "internet", "api call", "api_call",
        "web request", "web_request", "socket", "urllib", "requests", "fetch",
        "download", "upload", "outbound",
    ),
    Capability.FILE_WRITE: (
        "file_system_write", "file system", "write file", "write_file",
        "save to disk", "save_to_disk", "create file", "modify file",
        "file write", "disk write",
    ),
    Capability.FILE_READ: (
        "read file", "read_file", "file read", "open file", "load file",
        "file system read", "scan file", "filesystem",
    ),
    Capability.SUBPROCESS: (
        "shell", "subprocess", "os.system", "run command", "execute command",
        "shell_execution", "shell command", "spawn", "system call",
    ),
    Capability.DYNAMIC_CODE: (
        "eval", "exec(", "dynamic code", "compile(", "dynamic_code",
        "code execution", "code_execution",
    ),
    Capability.CREDENTIAL_ACCESS: (
        "credential", "api key", "api_key", "apikey", "token", "secret",
        "password", "auth", "private key", ".env",
    ),
    Capability.IDENTITY_WRITE: (
        "soul.md", "memory.md", "agents.md", "identity", "persona",
        "identity_file_modification", "system prompt", "system_prompt",
    ),
}


def normalize_declared(declared: list[str]) -> set[Capability]:
    """
    把声明的权限字符串列表归一到能力集合。

    白话讲解：逐条声明去和关键词表匹配（子串、忽略大小写），命中就记入对应能力。
    这样无论作者写 "network access" 还是 "requires HTTP"，都归到 NETWORK。
    """
    result: set[Capability] = set()
    for item in declared:
        text = item.lower()
        for capability, keywords in _DECLARED_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                result.add(capability)
    return result


# 动态引擎行为类型 → 能力
_BEHAVIOR_MAP: dict[BehaviorType, Capability] = {
    BehaviorType.FILE_OPEN: Capability.FILE_READ,
    BehaviorType.FILE_WRITE: Capability.FILE_WRITE,
    BehaviorType.NETWORK: Capability.NETWORK,
    BehaviorType.SUBPROCESS: Capability.SUBPROCESS,
    BehaviorType.DYNAMIC_CODE: Capability.DYNAMIC_CODE,
}


def observed_from_events(events: list[BehaviorEvent]) -> set[Capability]:
    """
    把沙箱审计到的行为事件列表归一到能力集合。

    白话讲解：每条事件带一个 BehaviorType，直接查表映射；OTHER 忽略。
    """
    result: set[Capability] = set()
    for event in events:
        capability = _BEHAVIOR_MAP.get(event.behavior)
        if capability is not None:
            result.add(capability)
    return result


def observed_from_audit(result: DynamicAuditResult) -> set[Capability]:
    """
    把动态审计的聚合结论归一到能力集合。

    白话讲解：DynamicAuditResult 已经把行为聚合成几组信号：
    - network_targets → NETWORK
    - subprocess_calls → SUBPROCESS
    - identity_files_written → IDENTITY_WRITE（篡改身份/记忆 = 控制面攻击）
    - honeypot_triggered → CREDENTIAL_ACCESS（读了假凭据）
    - findings 里带的 behavior 类型 → 兜底补充
    """
    caps: set[Capability] = set()
    if result.network_targets:
        caps.add(Capability.NETWORK)
    if result.subprocess_calls:
        caps.add(Capability.SUBPROCESS)
    if result.identity_files_written:
        caps.add(Capability.IDENTITY_WRITE)
    if result.honeypot_triggered:
        caps.add(Capability.CREDENTIAL_ACCESS)
    for finding in result.findings:
        capability = _BEHAVIOR_MAP.get(finding.behavior)
        if capability is not None:
            caps.add(capability)
    return caps
