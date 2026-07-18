"""
动态审计引擎 - 行为监控与研判

白话讲解：
- 沙箱（sandbox.py）负责"跑技能 + 记行为"，本文件负责"看行为清单 + 下结论"。
- 核心判据（从强到弱）：
  1. 蜜罐命中：假凭据的随机标记出现在网络/子进程参数里 → 数据外传铁证（最强）
  2. 身份文件篡改：写 SOUL.md/MEMORY.md/AGENTS.md → 持久化后门（ClawHavoc 手法）
  3. 读蜜罐诱饵文件 + 有网络外联 → 凭据窃取的典型组合
  4. 连已知恶意域名/IP（C2/外传服务）
  5. 起子进程执行 curl|bash 等远程脚本
- 把这些行为折算成 0-1 的动态风险分，并给出可读结论。
"""
from __future__ import annotations

from src.dynamic_engine.models import (
    BehaviorType,
    DynamicAuditResult,
    DynamicFinding,
    SandboxRunResult,
)

# 已知恶意/外传相关域名与 IP（ClawHavoc IOC + 常见匿名外传服务）
DEFAULT_SUSPICIOUS_TARGETS = [
    "91.92.242.30",
    "webhook.site",
    "glot.io",
    "pastebin.com",
    "transfer.sh",
    "requestbin",
    "ngrok.io",
    "ngrok-free.app",
    "discord.com/api/webhooks",
    "0x0.st",
    "tmpfiles.org",
]

# 敏感诱饵路径特征（读到这些 = 在翻凭据）
SENSITIVE_PATH_HINTS = [
    ".ssh/id_rsa",
    ".env",
    "credentials.json",
    ".clawdbot",
    ".config/openclaw",
    "/etc/passwd",
    "/etc/shadow",
]

# 远程脚本执行特征（子进程命令行里出现即高危）
REMOTE_EXEC_HINTS = ["curl", "wget", "| bash", "| sh", "bash -c", "base64"]


def analyze(
    run_result: SandboxRunResult,
    suspicious_targets: list[str] | None = None,
) -> DynamicAuditResult:
    """
    分析一次沙箱执行结果，产出动态审计结论

    白话讲解：遍历行为清单，按上面的判据累加风险分、生成发现列表
    """
    suspicious_targets = suspicious_targets or DEFAULT_SUSPICIOUS_TARGETS

    result = DynamicAuditResult(
        executed=run_result.executed,
        backend=run_result.backend,
        timed_out=run_result.timed_out,
        identity_files_written=list(run_result.identity_files_written),
        reason=run_result.reason,
    )

    # 沙箱没跑起来：风险分不可信，标记未执行交上层降级
    if not run_result.executed:
        result.findings.append(
            DynamicFinding("low", f"动态引擎未执行: {run_result.reason or '未知原因'}")
        )
        return result

    risk = 0.0

    # 1) 蜜罐命中（最强信号）
    honeypot_events = [e for e in run_result.events if e.hits_honeypot]
    if honeypot_events:
        result.honeypot_triggered = True
        risk += 0.70
        result.findings.append(DynamicFinding(
            "high",
            f"蜜罐诱捕命中：假凭据标记出现在 {len(honeypot_events)} 次外发行为中"
            "（凭据窃取并外传的铁证）",
            BehaviorType.NETWORK,
        ))

    # 2) 身份文件篡改（持久化后门）
    if run_result.identity_files_written:
        risk += 0.35
        result.findings.append(DynamicFinding(
            "high",
            f"篡改 Agent 身份文件: {', '.join(run_result.identity_files_written[:3])}"
            "（SOUL.md/MEMORY.md 后门持久化）",
            BehaviorType.FILE_WRITE,
        ))

    # 3) 网络行为
    network_targets: list[str] = []
    hit_suspicious = False
    for e in run_result.events:
        if e.behavior is BehaviorType.NETWORK:
            joined = " ".join(e.args)
            network_targets.append(joined[:120])
            for t in suspicious_targets:
                if t in joined:
                    hit_suspicious = True
    result.network_targets = network_targets
    if hit_suspicious:
        risk += 0.30
        result.findings.append(DynamicFinding(
            "high", "连接已知恶意域名/外传服务（C2 或数据外传）", BehaviorType.NETWORK
        ))

    # 4) 读敏感诱饵文件
    read_sensitive = False
    for e in run_result.events:
        if e.behavior is BehaviorType.FILE_OPEN:
            joined = " ".join(e.args)
            if any(h in joined for h in SENSITIVE_PATH_HINTS):
                read_sensitive = True
                break

    # 5) 子进程 / 远程脚本执行
    subprocess_calls: list[str] = []
    remote_exec = False
    for e in run_result.events:
        if e.behavior is BehaviorType.SUBPROCESS:
            joined = " ".join(e.args)
            subprocess_calls.append(joined[:120])
            if any(h in joined for h in REMOTE_EXEC_HINTS):
                remote_exec = True
    result.subprocess_calls = subprocess_calls
    if remote_exec:
        risk += 0.30
        result.findings.append(DynamicFinding(
            "high", "子进程执行远程下载/脚本命令（curl|bash 等）", BehaviorType.SUBPROCESS
        ))

    # 组合信号：读了凭据又有网络外联（即使没直接抓到标记也高度可疑）
    if read_sensitive and network_targets:
        risk += 0.40
        result.findings.append(DynamicFinding(
            "high", "读取敏感凭据文件后发起网络外联（凭据外传典型组合）",
            BehaviorType.NETWORK,
        ))
    elif read_sensitive:
        risk += 0.15
        result.findings.append(DynamicFinding(
            "medium", "读取敏感凭据/诱饵文件", BehaviorType.FILE_OPEN
        ))

    # 纯网络外联（无上述强信号时的弱加分）
    if network_targets and not (hit_suspicious or honeypot_events or read_sensitive):
        risk += 0.10
        result.findings.append(DynamicFinding(
            "low", f"存在网络外联行为（{len(network_targets)} 次）", BehaviorType.NETWORK
        ))

    if not result.findings:
        result.findings.append(DynamicFinding("low", "沙箱执行未发现明显恶意行为"))

    result.risk_score = min(1.0, risk)
    return result
