"""
静态审计引擎 - Semgrep + Bandit + pip-audit 集成
把解析器提取出的代码块送给安全扫描工具，收集扫描结果

白话讲解：
- 解析器（skill_parser.py）负责"拆开" SKILL.md，提取代码块
- 本文件负责把代码块"送检"——分别丢给 Semgrep 和 Bandit 扫描
- 为什么用两个工具？因为它们各有所长：
  - Semgrep：基于模式匹配，可以写自定义规则（比如检测 os.system 调用）
  - Bandit：专门针对 Python 安全问题（比如硬编码密码、SQL注入）
- 两个工具的结果合并，才能更全面地发现问题
"""
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScanFinding:
    """
    单条扫描发现

    白话讲解：每个工具扫描出的每条问题，都用这个结构来装
    统一格式方便后续汇总和展示
    """
    tool: str                    # 来自哪个工具：semgrep / bandit / pip-audit
    rule_id: str                 # 规则ID（比如 bandit 的 B602 = subprocess调用）
    severity: str                # 严重程度：high / medium / low
    message: str                 # 问题描述
    file_path: str = ""          # 出问题的文件路径
    line_number: int = 0         # 出问题的行号
    code_snippet: str = ""       # 出问题的代码片段


@dataclass
class ScanReport:
    """
    一次扫描的完整报告

    白话讲解：把所有工具的所有发现收集到一起
    还统计了各严重等级的数量，方便快速判断风险
    """
    findings: list[ScanFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # 工具执行错误（比如超时）

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "medium")

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "low")

    def summary(self) -> str:
        """生成一行摘要"""
        if not self.findings:
            return "未发现安全问题"
        return (
            f"发现 {self.total_findings} 个问题 "
            f"(高危:{self.high_count} 中危:{self.medium_count} 低危:{self.low_count})"
        )


def _write_code_to_temp(code: str, suffix: str = ".py") -> Path:
    """
    把代码写入临时文件，返回文件路径

    白话讲解：Semgrep 和 Bandit 都需要扫描"文件"，不能直接接收字符串
    所以我们把代码块写到临时文件里，扫描完再删掉
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    tmp.write(code)
    tmp.close()
    return Path(tmp.name)


def run_semgrep(
    code: str,
    rules_dir: str = "config/semgrep_rules",
    timeout: int = 120,
) -> list[ScanFinding]:
    """
    用 Semgrep 扫描代码

    白话讲解：
    1. 把代码写到临时文件
    2. 调用 semgrep 命令行工具扫描
    3. 解析 JSON 格式的扫描结果
    4. 转换成我们的 ScanFinding 格式

    如果 config/semgrep_rules 目录下没有自定义规则，
    就用 semgrep 内置的 auto 规则（能检测常见安全问题）
    """
    tmp_file = _write_code_to_temp(code)
    findings = []

    try:
        # 检查自定义规则目录是否存在且非空
        rules_path = Path(rules_dir)
        if rules_path.exists() and any(rules_path.iterdir()):
            config = str(rules_path)
        else:
            # 没有自定义规则就用内置规则
            config = "auto"

        cmd = [
            "semgrep", "scan",
            "--config", config,
            "--json",                     # JSON输出方便解析
            "--no-git-ignore",            # 不跳过gitignore的文件
            "--timeout", str(timeout),
            str(tmp_file),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # 解析 JSON 结果
        if result.stdout:
            data = json.loads(result.stdout)
            for match in data.get("results", []):
                severity_map = {
                    "ERROR": "high",
                    "WARNING": "medium",
                    "INFO": "low",
                }
                findings.append(ScanFinding(
                    tool="semgrep",
                    rule_id=match.get("check_id", "unknown"),
                    severity=severity_map.get(
                        match.get("extra", {}).get("severity", "WARNING"), "medium"
                    ),
                    message=match.get("extra", {}).get("message", ""),
                    file_path=str(tmp_file),
                    line_number=match.get("start", {}).get("line", 0),
                    code_snippet=match.get("extra", {}).get("lines", ""),
                ))
    except subprocess.TimeoutExpired:
        findings.append(ScanFinding(
            tool="semgrep", rule_id="TIMEOUT", severity="medium",
            message=f"Semgrep 扫描超时 ({timeout}s)"
        ))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        findings.append(ScanFinding(
            tool="semgrep", rule_id="ERROR", severity="low",
            message=f"Semgrep 执行错误: {e}"
        ))
    finally:
        tmp_file.unlink(missing_ok=True)  # 删除临时文件

    return findings


def run_bandit(
    code: str,
    severity_threshold: str = "medium",
    confidence_threshold: str = "medium",
) -> list[ScanFinding]:
    """
    用 Bandit 扫描 Python 代码

    白话讲解：
    Bandit 是 Python 专用的安全扫描器，能检测：
    - B602: subprocess 调用（可能执行任意命令）
    - B605: os.system 调用（更危险的命令执行）
    - B301: pickle 反序列化（可能执行恶意代码）
    - B105: 硬编码密码
    - 等等几十条规则

    severity_threshold 控制报告门槛，medium = 只报告中危及以上
    """
    tmp_file = _write_code_to_temp(code)
    findings = []

    # Bandit 的严重等级映射：ll=low, mm=medium, hh=high
    level_map = {"low": "l", "medium": "m", "high": "h"}
    sev = level_map.get(severity_threshold, "m")
    conf = level_map.get(confidence_threshold, "m")

    try:
        cmd = [
            "bandit",
            "-f", "json",               # JSON输出
            f"-l",                       # 报告低危及以上（我们在代码层面过滤）
            str(tmp_file),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Bandit 发现问题时返回码是1，不是错误
        if result.stdout:
            data = json.loads(result.stdout)
            for issue in data.get("results", []):
                severity = issue.get("issue_severity", "MEDIUM").lower()
                confidence = issue.get("issue_confidence", "MEDIUM").lower()

                # 按阈值过滤
                sev_order = {"low": 0, "medium": 1, "high": 2}
                if sev_order.get(severity, 0) < sev_order.get(severity_threshold, 1):
                    continue

                findings.append(ScanFinding(
                    tool="bandit",
                    rule_id=issue.get("test_id", "unknown"),
                    severity=severity,
                    message=issue.get("issue_text", ""),
                    file_path=str(tmp_file),
                    line_number=issue.get("line_number", 0),
                    code_snippet=issue.get("code", ""),
                ))
    except subprocess.TimeoutExpired:
        findings.append(ScanFinding(
            tool="bandit", rule_id="TIMEOUT", severity="medium",
            message="Bandit 扫描超时 (60s)"
        ))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        findings.append(ScanFinding(
            tool="bandit", rule_id="ERROR", severity="low",
            message=f"Bandit 执行错误: {e}"
        ))
    finally:
        tmp_file.unlink(missing_ok=True)

    return findings


def run_pip_audit(requirements_content: str, timeout: int = 60) -> list[ScanFinding]:
    """
    用 pip-audit 扫描依赖漏洞

    白话讲解：
    有些技能会在 requirements.txt 里指定依赖包
    pip-audit 会检查这些包是否有已知漏洞（CVE）
    比如某个版本的 requests 有安全漏洞，就会报出来
    """
    tmp_file = _write_code_to_temp(requirements_content, suffix=".txt")
    findings = []

    try:
        cmd = [
            "pip-audit",
            "-r", str(tmp_file),         # 扫描 requirements 文件
            "-f", "json",                # JSON输出
            "--no-deps",                 # 不检查间接依赖（加速）
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.stdout:
            data = json.loads(result.stdout)
            for vuln in data.get("dependencies", []):
                for v in vuln.get("vulns", []):
                    findings.append(ScanFinding(
                        tool="pip-audit",
                        rule_id=v.get("id", "unknown"),     # CVE编号
                        severity="high",                      # 已知漏洞都算高危
                        message=f"{vuln.get('name')}=={vuln.get('version')}: {v.get('description', '')}",
                    ))
    except subprocess.TimeoutExpired:
        findings.append(ScanFinding(
            tool="pip-audit", rule_id="TIMEOUT", severity="medium",
            message=f"pip-audit 扫描超时 ({timeout}s)"
        ))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        findings.append(ScanFinding(
            tool="pip-audit", rule_id="ERROR", severity="low",
            message=f"pip-audit 执行错误: {e}"
        ))
    finally:
        tmp_file.unlink(missing_ok=True)

    return findings


def scan_code_blocks(
    code_blocks: list[str],
    code_languages: list[str],
    semgrep_rules_dir: str = "config/semgrep_rules",
    bandit_severity: str = "medium",
    bandit_confidence: str = "medium",
) -> ScanReport:
    """
    对所有代码块执行静态扫描（主入口）

    白话讲解：
    这是静态引擎的"总调度"函数
    1. 遍历解析器提取出的每个代码块
    2. Python 代码 → 同时用 Semgrep 和 Bandit 扫
    3. Bash/Shell 代码 → 只用 Semgrep 扫（Bandit 只管 Python）
    4. 其他语言 → 只用 Semgrep 扫
    5. 把所有结果汇总到 ScanReport 里返回
    """
    report = ScanReport()

    for i, (code, lang) in enumerate(zip(code_blocks, code_languages)):
        if not code.strip():
            continue

        # Semgrep 对所有语言都能扫
        try:
            semgrep_findings = run_semgrep(code, rules_dir=semgrep_rules_dir)
            report.findings.extend(semgrep_findings)
        except Exception as e:
            report.errors.append(f"代码块{i} Semgrep 错误: {e}")

        # Bandit 只扫 Python 代码
        if lang.lower() in ("python", "py", "unknown"):
            try:
                bandit_findings = run_bandit(
                    code,
                    severity_threshold=bandit_severity,
                    confidence_threshold=bandit_confidence,
                )
                report.findings.extend(bandit_findings)
            except Exception as e:
                report.errors.append(f"代码块{i} Bandit 错误: {e}")

    return report
