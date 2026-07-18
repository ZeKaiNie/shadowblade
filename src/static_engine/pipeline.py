"""
静态审计主流水线 - 把 S1 解析、S2/S3 扫描、AI 研判串起来跑端到端

白话讲解：
- 之前每个模块（skill_parser/scanner/llm_judge）都能独立跑
- 这里把它们按顺序串起来：解析 → 扫描代码 → AI 研判 → 综合打分
- 输出统一的 SkillAuditResult，方便后续 FastAPI、Streamlit 直接用

设计原则：
1. **可控性**：LLM 调用可关（enable_llm=False），方便不依赖 vLLM 跑测试
2. **韧性**：任一引擎失败不影响其他引擎，结果里标记哪些引擎实际跑了
3. **可解释**：每个引擎单独打分（static_risk / ai_risk），便于前端展示
4. **轻量综合**：用加权平均，没启用的引擎权重自动剔除并归一化
"""
from pathlib import Path
from typing import Optional

from src.static_engine.models import (
    RiskLevel,
    SkillAuditResult,
    SkillMetadata,
)
from src.static_engine.scanner import ScanReport, scan_code_blocks
from src.static_engine.skill_parser import parse_skill_md

# ---------- 静态引擎评分 ----------

def _score_static_findings(
    metadata: SkillMetadata,
    scan_report: Optional[ScanReport],
) -> tuple[float, list[str]]:
    """
    根据解析阶段的标记 + 扫描器的发现，计算静态风险分

    白话讲解：
    静态分由三部分组成：
    1. 解析阶段的"快速指标"：可疑关键词、Unicode 隐写
    2. Prerequisites 段落特殊检查（ClawHavoc 主攻入口）
    3. 扫描器的具体发现：Semgrep / Bandit 报出的安全问题

    评分逻辑（risk 0-1，越高越危险）：
    - ASCII 隐写  → +0.50（强信号，几乎一定是恶意）
    - 每个 high finding → +0.20，最多累计到 0.6
    - 每个 medium finding → +0.10
    - 每个 low finding → +0.03
    - 每个可疑关键词匹配 → +0.05
    - 危险组合关键词（curl + id_rsa 等）→ 额外 +0.20
    - Prerequisites 含下载/执行命令 → +0.30（ClawHavoc 典型）
    - Curl/wget 管道到 bash/sh → +0.30（远程脚本执行）

    返回:
        (risk_score, findings_text_list) 风险分与可读发现列表
    """
    risk = 0.0
    findings_text: list[str] = []

    # 1. ASCII Unicode 隐写（强信号）
    if metadata.has_ascii_smuggling:
        risk += 0.50
        findings_text.append("[严重] 检测到 Unicode 隐写字符（ASCII smuggling 攻击）")

    # 2. 可疑关键词
    if metadata.matched_patterns:
        kw_score = min(0.30, len(metadata.matched_patterns) * 0.05)
        risk += kw_score
        findings_text.append(
            f"[警告] 匹配可疑关键词 {len(metadata.matched_patterns)} 个: "
            f"{', '.join(metadata.matched_patterns[:8])}"
        )

        # 危险组合（数据窃取的典型特征）
        # 白话讲解：单独 curl 不一定恶意，但 curl+id_rsa 几乎是数据外传
        dangerous_set = set(p.lower() for p in metadata.matched_patterns)
        combos = [
            ({"curl", "id_rsa"}, "curl + id_rsa（SSH 密钥外传）"),
            ({"wget", "id_rsa"}, "wget + id_rsa（SSH 密钥外传）"),
            ({"curl", "webhook.site"}, "curl + webhook.site（C2 回调）"),
            ({"base64", "eval"}, "base64 + eval（混淆代码执行）"),
            ({"bash -c", "curl"}, "bash -c + curl（远程脚本执行）"),
            # 同时使用两种下载工具是异常信号（正常技能很少需要 curl 又用 wget）
            ({"curl", "wget"}, "curl + wget（多重下载工具，可疑分发模式）"),
        ]
        for combo, desc in combos:
            if combo.issubset(dangerous_set):
                risk += 0.20
                findings_text.append(f"[严重] 危险组合: {desc}")

    # 3. Prerequisites 段落深度检查
    # 白话讲解：ClawHavoc 攻击的核心入口就在 prerequisites
    # "Before using install dependencies" → 然后 curl | bash 偷数据
    # 任何在 prerequisites 出现的 curl/wget/bash 都是高度可疑
    prereq_lower = (metadata.prerequisites or "").lower()
    if prereq_lower:
        # 远程下载/执行类
        prereq_dangerous = []
        for danger_kw in ("curl", "wget", "bash -c", " | bash", " | sh", "base64"):
            if danger_kw in prereq_lower:
                prereq_dangerous.append(danger_kw.strip())
        if prereq_dangerous:
            risk += 0.30
            findings_text.append(
                f"[严重] Prerequisites 段落含远程下载/执行命令 "
                f"({', '.join(prereq_dangerous)})——ClawHavoc 攻击典型入口"
            )

        # 管道到 shell 是远程脚本执行的特征（curl ... | bash）
        if "| bash" in prereq_lower or "| sh" in prereq_lower:
            risk += 0.10  # 在前面已加过基础分，这里追加管道特征加成
            findings_text.append(
                "[严重] 检测到 'curl/wget | bash' 管道模式（无校验远程脚本执行）"
            )

        # 破坏性 / 提权命令检查
        # 白话讲解：正常的 prerequisites 应该只是 `pip install xxx`、`npm i xxx`
        # 出现 rm -rf、chmod 000、sudo systemctl stop 这些是典型的破坏型恶意技能
        destructive_patterns = [
            ("rm -rf", "递归强制删除"),
            ("chmod 000", "锁定关键文件"),
            ("chmod 777", "解除文件权限保护"),
            ("sudo systemctl stop", "停止系统服务（可能是日志/审计）"),
            ("systemctl stop rsyslog", "停止系统日志（反取证）"),
            ("systemctl stop auditd", "停止审计服务（反取证）"),
            ("/etc/passwd", "操作 passwd 文件"),
            ("/etc/shadow", "操作 shadow 文件"),
        ]
        destructive_hits = [
            desc for kw, desc in destructive_patterns if kw in prereq_lower
        ]
        if destructive_hits:
            risk += 0.40   # 强信号：正常技能不会有这些
            findings_text.append(
                f"[严重] Prerequisites 段落含破坏性/反取证命令: {'; '.join(destructive_hits[:3])}"
            )

    # 4. 代码块深度检查（数据外传 endpoint + 凭据收集）
    # 白话讲解：高级恶意技能不用 curl/wget，改用 urllib/requests 把数据发到匿名服务
    # pastebin.com / glot.io / transfer.sh 这些被广泛用作 exfil 的临时存储
    exfil_endpoints = [
        "pastebin.com",
        "glot.io",
        "transfer.sh",
        "webhook.site",
        "requestbin",
        "discord.com/api/webhooks",
        "ngrok.io",
        "ngrok-free.app",
        "tmpfiles.org",
        "0x0.st",
    ]
    code_full_text = " ".join(metadata.code_blocks).lower()
    if code_full_text:
        hit_endpoints = [ep for ep in exfil_endpoints if ep in code_full_text]
        if hit_endpoints:
            risk += 0.35
            findings_text.append(
                f"[严重] 代码块包含已知数据外传服务: {', '.join(hit_endpoints[:3])}"
            )

        # 凭据收集 + 网络库 = 凭据外传典型特征
        # 白话讲解：os.environ 读环境变量本身正常，但配合 urllib/requests
        # 把环境变量"发出去"就是凭据窃取（很多正常技能根本不需要枚举 env）
        cred_collection = (
            "os.environ" in code_full_text
            or "os.getenv" in code_full_text
            or "process.env" in code_full_text
        )
        net_send = any(
            kw in code_full_text
            for kw in (
                "urllib.request.urlopen",
                "requests.post",
                "requests.put",
                "httpx.post",
                "fetch(",
                "xmlhttprequest",
            )
        )
        if cred_collection and net_send:
            risk += 0.30
            findings_text.append(
                "[严重] 代码块同时包含环境变量枚举 + 网络发送（凭据外传特征）"
            )

        # shutil.rmtree 配合敏感目录 = 破坏型攻击
        if "shutil.rmtree" in code_full_text and any(
            danger_path in code_full_text
            for danger_path in ("~/.ssh", "/var/log", "/etc/", "/root/")
        ):
            risk += 0.30
            findings_text.append(
                "[严重] 代码使用 shutil.rmtree 删除敏感目录（破坏性攻击）"
            )

    # 3. 扫描器发现（Semgrep + Bandit）
    if scan_report is not None:
        if scan_report.high_count > 0:
            # 每个 high 加 0.20，但累计上限 0.6（避免单一类型刷分）
            high_score = min(0.60, scan_report.high_count * 0.20)
            risk += high_score
            findings_text.append(
                f"[高危] 扫描器发现 {scan_report.high_count} 个高危问题"
            )
        if scan_report.medium_count > 0:
            risk += min(0.30, scan_report.medium_count * 0.10)
            findings_text.append(
                f"[中危] 扫描器发现 {scan_report.medium_count} 个中危问题"
            )
        if scan_report.low_count > 0:
            risk += min(0.15, scan_report.low_count * 0.03)

        # 把每个具体发现写进列表（限量，避免太长）
        for f in scan_report.findings[:10]:
            findings_text.append(
                f"[{f.tool}/{f.rule_id}] {f.severity}: {f.message[:120]}"
            )

    # 上限保护：风险分不能超过 1.0
    return min(1.0, risk), findings_text


# ---------- 风险等级映射 ----------

def _risk_score_to_level(risk_score: float) -> RiskLevel:
    """
    把 0-1 的风险分映射到 5 档风险等级

    白话讲解：和 settings.yaml 的阈值对齐（注意 yaml 用 0-100，我们用 0-1）：
    - <0.20 (>80 分): SAFE
    - 0.20-0.40: LOW
    - 0.40-0.60: MEDIUM
    - 0.60-0.80: HIGH
    - ≥0.80: CRITICAL
    """
    if risk_score >= 0.80:
        return RiskLevel.CRITICAL
    if risk_score >= 0.60:
        return RiskLevel.HIGH
    if risk_score >= 0.40:
        return RiskLevel.MEDIUM
    if risk_score >= 0.20:
        return RiskLevel.LOW
    return RiskLevel.SAFE


# ---------- 综合评分（加权平均） ----------

def _combine_scores(
    static_risk: float,
    ai_risk: float,
    static_enabled: bool,
    ai_enabled: bool,
    dynamic_risk: float = 0.0,
    dynamic_enabled: bool = False,
    static_weight: float = 0.4,
    dynamic_weight: float = 0.35,
    ai_weight: float = 0.25,
) -> float:
    """
    把各引擎的风险分加权综合成最终风险分

    白话讲解：
    - 用加权平均；只对**实际启用**的引擎计算（未启用的引擎自动剔除）
    - 权重会自动归一化：只有静态时 = 100% 静态；三个都开时按 0.4/0.35/0.25
    - 权重与 config/settings.yaml 的 trust_score.weights 对齐

    设计上不直接把"未启用引擎"算 0，因为那等于宣称"该引擎确认安全"，
    会冲淡其他引擎的告警。

    返回: 综合风险分 (0-1)
    """
    weights = {}
    scores = {}
    if static_enabled:
        weights["static"] = static_weight
        scores["static"] = static_risk
    if dynamic_enabled:
        weights["dynamic"] = dynamic_weight
        scores["dynamic"] = dynamic_risk
    if ai_enabled:
        weights["ai"] = ai_weight
        scores["ai"] = ai_risk

    if not weights:
        # 所有引擎都没启用 → 没法判断，给个保守的中等分
        return 0.5

    total_weight = sum(weights.values())
    # 归一化加权平均
    return sum(scores[k] * weights[k] / total_weight for k in weights)


# ---------- 主入口 ----------

def audit_skill(
    skill_md_content: str,
    enable_static_scan: bool = True,
    enable_llm: bool = False,
    enable_dynamic: bool = False,
    semgrep_rules_dir: str = "config/semgrep_rules",
    bandit_severity: str = "low",
    suspicious_patterns: Optional[list[str]] = None,
    # LLM 相关参数（仅在 enable_llm=True 时生效）
    llm_api_base: str = "http://127.0.0.1:8000/v1",
    llm_model: str = "models/qwen3-4b-awq",
    llm_api_key: Optional[str] = None,
    rag_knowledge_base=None,
    # 动态引擎参数（仅在 enable_dynamic=True 时生效）
    dynamic_backend: str = "auto",
    dynamic_image: str = "python:3.11-slim",
    dynamic_timeout: int = 60,
    dynamic_allow_unsafe_subprocess: bool = False,
) -> SkillAuditResult:
    """
    静态审计主流水线（接收 SKILL.md 字符串）

    白话讲解：
    1. **S1**: 解析 SKILL.md → 拆出技能名、权限、代码块、可疑标记
    2. **S2+S3**: Semgrep + Bandit 扫描代码块（可关）
    3. **AI 研判**: SSD 四子任务给出 risk_score（可关，默认关）
    4. **综合**: 加权平均得到最终 risk_score → 映射到 5 档 RiskLevel

    参数:
        skill_md_content: SKILL.md 原文
        enable_static_scan: 是否跑 Semgrep/Bandit（默认 True，关掉只用解析阶段标记）
        enable_llm: 是否跑 LLM 研判（默认 False，因为依赖 vLLM/云端服务）
        semgrep_rules_dir: 自定义 Semgrep 规则目录
        bandit_severity: Bandit 报告门槛（low / medium / high）
        suspicious_patterns: 可疑关键词列表（不传用 skill_parser 默认列表）
        llm_api_base / llm_model / llm_api_key: LLM 端点配置
        rag_knowledge_base: RAG 知识库实例（可选，提升 LLM 准确度）

    返回:
        SkillAuditResult 完整审计结果
    """
    # ===== 步骤 1：S1 解析 =====
    metadata = parse_skill_md(
        skill_md_content,
        suspicious_patterns=suspicious_patterns,
    )

    # ===== 步骤 2：S2+S3 静态扫描（可关） =====
    scan_report: Optional[ScanReport] = None
    if enable_static_scan and metadata.code_blocks:
        try:
            scan_report = scan_code_blocks(
                metadata.code_blocks,
                metadata.code_language,
                semgrep_rules_dir=semgrep_rules_dir,
                bandit_severity=bandit_severity,
            )
        except Exception as e:
            # 单个引擎失败不影响整体；记录但继续
            scan_report = ScanReport()
            scan_report.errors.append(f"扫描器异常: {e}")

    # 计算静态风险分
    static_risk, static_findings = _score_static_findings(metadata, scan_report)

    # ===== 步骤 3：AI 研判（可关） =====
    ai_risk = 0.0
    ai_findings: list[str] = []
    ai_enabled_actual = False

    if enable_llm:
        try:
            # 延迟 import，避免没启用 LLM 时也加载这个模块
            from src.ai_engine.llm_judge import judge_skill_ssd

            judgment = judge_skill_ssd(
                skill_name=metadata.name,
                description=metadata.description,
                prerequisites=metadata.prerequisites,
                code_blocks=metadata.code_blocks,
                capabilities=metadata.declared_capabilities,
                matched_patterns=metadata.matched_patterns,
                skill_body=metadata.raw_content,
                api_base=llm_api_base,
                model=llm_model,
                api_key=llm_api_key,
                rag_knowledge_base=rag_knowledge_base,
            )
            ai_risk = judgment.risk_score
            ai_findings = list(judgment.findings) if judgment.findings else []
            if judgment.reasoning:
                ai_findings.insert(0, f"[LLM] {judgment.reasoning[:300]}")
            # 只有真的拿到结果才算启用成功
            ai_enabled_actual = "ERROR" not in str(judgment.findings)
        except Exception as e:
            ai_findings = [f"[LLM ERROR] {e}"]
            ai_enabled_actual = False

    # ===== 步骤 3.5：动态沙箱研判（可关，默认关） =====
    dynamic_risk = 0.0
    dynamic_findings: list[str] = []
    dynamic_enabled_actual = False
    dynamic_identity_written: list[str] = []

    if enable_dynamic and metadata.code_blocks:
        try:
            # 延迟 import，避免没启用动态引擎时也加载 docker/harness 相关模块
            from src.dynamic_engine.pipeline import audit_dynamic

            dyn = audit_dynamic(
                code_blocks=metadata.code_blocks,
                code_languages=metadata.code_language,
                backend=dynamic_backend,
                image=dynamic_image,
                timeout=dynamic_timeout,
                allow_unsafe_subprocess=dynamic_allow_unsafe_subprocess,
            )
            dynamic_risk = dyn.risk_score
            dynamic_findings = dyn.finding_texts
            dynamic_identity_written = dyn.identity_files_written
            # 只有沙箱真的跑起来了，动态分才计入综合评分
            dynamic_enabled_actual = dyn.executed
            if not dyn.executed and dyn.reason:
                dynamic_findings.insert(0, f"[动态引擎未执行] {dyn.reason}")
        except Exception as e:
            dynamic_findings = [f"[动态引擎 ERROR] {e}"]
            dynamic_enabled_actual = False

    # ===== 步骤 4：综合评分 =====
    final_risk = _combine_scores(
        static_risk=static_risk,
        ai_risk=ai_risk,
        static_enabled=True,
        ai_enabled=ai_enabled_actual,
        dynamic_risk=dynamic_risk,
        dynamic_enabled=dynamic_enabled_actual,
    )
    final_trust = 1.0 - final_risk
    risk_level = _risk_score_to_level(final_risk)

    # ===== 步骤 5：生成摘要 =====
    summary = _generate_summary(metadata, risk_level, final_risk, static_findings, ai_findings)

    return SkillAuditResult(
        skill_name=metadata.name or "unknown",
        risk_level=risk_level,
        trust_score=final_trust,
        risk_score=final_risk,
        static_findings=static_findings,
        dynamic_findings=dynamic_findings,
        ai_findings=ai_findings,
        static_risk=static_risk,
        dynamic_risk=dynamic_risk,
        ai_risk=ai_risk,
        static_enabled=True,
        dynamic_enabled=dynamic_enabled_actual,
        ai_enabled=ai_enabled_actual,
        declared_capabilities=metadata.declared_capabilities,
        actual_capabilities=dynamic_identity_written,   # 动态观测到的敏感写入行为
        permission_mismatch=False,    # 待 S6 实现
        has_suspicious_patterns=metadata.has_suspicious_patterns,
        matched_patterns=metadata.matched_patterns,
        has_ascii_smuggling=metadata.has_ascii_smuggling,
        summary=summary,
    )


def audit_skill_from_file(
    skill_md_path: str | Path,
    **kwargs,
) -> SkillAuditResult:
    """
    便捷入口：从文件路径审计

    白话讲解：包装 audit_skill 接收 Path，方便命令行/脚本调用
    """
    path = Path(skill_md_path)
    if not path.exists():
        raise FileNotFoundError(f"SKILL.md 文件不存在: {path}")
    content = path.read_text(encoding="utf-8")
    return audit_skill(content, **kwargs)


def _generate_summary(
    metadata: SkillMetadata,
    risk_level: RiskLevel,
    risk_score: float,
    static_findings: list[str],
    ai_findings: list[str],
) -> str:
    """
    生成一段人类可读的审计结论

    白话讲解：
    给前端展示用的"一句话总结"，让用户快速理解结果
    后续可以让 LLM 生成更精炼的版本（M3 优化点）
    """
    name = metadata.name or "未命名技能"
    level_zh = {
        RiskLevel.CRITICAL: "严重风险",
        RiskLevel.HIGH: "高风险",
        RiskLevel.MEDIUM: "中等风险",
        RiskLevel.LOW: "低风险",
        RiskLevel.SAFE: "安全",
    }[risk_level]

    parts = [f"技能「{name}」综合评估为 **{level_zh}**（风险分 {risk_score:.2f}）"]

    if metadata.has_ascii_smuggling:
        parts.append("检出 Unicode 隐写字符")
    if metadata.matched_patterns:
        parts.append(f"匹配可疑关键词 {len(metadata.matched_patterns)} 个")

    static_high = sum(1 for f in static_findings if "[严重]" in f or "[高危]" in f)
    if static_high:
        parts.append(f"静态扫描有 {static_high} 项高危/严重发现")

    if ai_findings:
        parts.append("AI 研判已介入")

    return "；".join(parts) + "。"
