"""
动态审计引擎 - 数据模型

白话讲解：
- 静态引擎是"看代码"（不运行），动态引擎是"跑代码看它干了什么"
- 我们把技能代码丢进隔离沙箱里真的执行一遍，记录它的"行为"：
  读了哪些文件？连了哪些网络地址？起了哪些子进程？
- 这个文件定义这些"行为记录"和"动态审计结论"的结构化表示
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BehaviorType(str, Enum):
    """
    行为事件类型

    白话讲解：技能在沙箱里运行时可能做的几类"敏感动作"
    我们只关心这几类安全相关的行为，其余（如纯计算）忽略
    """
    FILE_OPEN = "file_open"          # 打开/读取文件
    FILE_WRITE = "file_write"        # 写入文件
    NETWORK = "network"              # 网络连接（socket/urllib/http）
    SUBPROCESS = "subprocess"        # 起子进程（os.system/subprocess）
    DYNAMIC_CODE = "dynamic_code"    # 动态执行代码（eval/exec/compile）
    OTHER = "other"                  # 其他被审计到的事件


@dataclass
class BehaviorEvent:
    """
    单条运行时行为事件

    白话讲解：沙箱里每发生一次敏感动作，就记一条
    - event: CPython 审计事件名（如 open, socket.connect, subprocess.Popen）
    - args: 该动作的参数（如打开的文件名、连接的地址、命令行）
    - hits_honeypot: 该动作的参数里是否出现了蜜罐标记（命中=数据外传铁证）
    """
    behavior: BehaviorType
    event: str
    args: list[str] = field(default_factory=list)
    hits_honeypot: bool = False

    def to_dict(self) -> dict:
        return {
            "behavior": self.behavior.value,
            "event": self.event,
            "args": self.args,
            "hits_honeypot": self.hits_honeypot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BehaviorEvent":
        return cls(
            behavior=BehaviorType(d.get("behavior", "other")),
            event=d.get("event", ""),
            args=list(d.get("args", [])),
            hits_honeypot=bool(d.get("hits_honeypot", False)),
        )


@dataclass
class SandboxRunResult:
    """
    沙箱一次执行的原始产物

    白话讲解：把"技能在沙箱里跑了一次"的所有第一手材料装起来
    - executed: 是否真的执行了（Docker 不可用 / 拉镜像失败时为 False）
    - backend: 用哪种后端跑的（docker / subprocess）
    - events: 审计到的行为事件列表
    - stdout/stderr: 执行输出
    - identity_files_written: 被写入的身份文件（SOUL.md/MEMORY.md/AGENTS.md）
    - reason: 未执行时的原因说明
    """
    executed: bool = False
    backend: str = "none"
    events: list[BehaviorEvent] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    identity_files_written: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class DynamicFinding:
    """
    单条动态审计发现

    白话讲解：监控器分析完行为事件后，得出的一条可读结论
    severity: high / medium / low
    """
    severity: str
    message: str
    behavior: BehaviorType = BehaviorType.OTHER


@dataclass
class DynamicAuditResult:
    """
    动态审计的完整结论

    白话讲解：动态引擎对一个技能的最终判断
    - risk_score: 动态风险分 0-1，越高越危险
    - executed: 沙箱是否真的跑起来了（没跑起来 risk 不可信，交给上层降级处理）
    - findings: 可读发现列表
    - honeypot_triggered: 蜜罐是否被触发（读了假凭据并试图外传）
    """
    risk_score: float = 0.0
    executed: bool = False
    backend: str = "none"
    findings: list[DynamicFinding] = field(default_factory=list)
    honeypot_triggered: bool = False
    network_targets: list[str] = field(default_factory=list)
    subprocess_calls: list[str] = field(default_factory=list)
    identity_files_written: list[str] = field(default_factory=list)
    # 读取到的敏感凭据/蜜罐诱饵文件路径（读它们=在翻凭据，映射为 credential_access 能力）
    credential_read_paths: list[str] = field(default_factory=list)
    timed_out: bool = False
    reason: str = ""

    @property
    def finding_texts(self) -> list[str]:
        """把 findings 转成纯文本列表，方便塞进 SkillAuditResult.dynamic_findings"""
        return [f"[{f.severity}] {f.message}" for f in self.findings]
