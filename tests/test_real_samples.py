"""
真实样本集成测试
用 ClawHavoc/ToxicSkills 模式的样本验证整个静态审计流水线
"""
from pathlib import Path

import pytest

from src.static_engine.skill_parser import parse_skill_from_file
from src.static_engine.scanner import scan_code_blocks


MALICIOUS_DIR = Path("data/malicious")
BENIGN_DIR = Path("data/benign")


def get_malicious_files():
    if MALICIOUS_DIR.exists():
        return sorted(MALICIOUS_DIR.glob("*.md"))
    return []


def get_benign_files():
    if BENIGN_DIR.exists():
        return sorted(BENIGN_DIR.glob("*.md"))
    return []


class TestMaliciousSamples:
    """所有恶意样本都应触发至少一个告警"""

    @pytest.mark.parametrize("skill_file", get_malicious_files(),
                             ids=lambda f: f.stem)
    def test_malicious_detected(self, skill_file):
        """恶意样本应被标记为可疑"""
        metadata = parse_skill_from_file(skill_file)

        # 至少满足以下一个条件：
        # 1. 有可疑关键词
        # 2. 有 ASCII 隐写
        # 3. 代码块扫描有发现
        has_alert = metadata.has_suspicious_patterns or metadata.has_ascii_smuggling

        if metadata.code_blocks:
            report = scan_code_blocks(
                metadata.code_blocks,
                metadata.code_language,
                bandit_severity="low",
            )
            has_alert = has_alert or report.total_findings > 0

        assert has_alert, (
            f"恶意样本 {skill_file.name} 未触发任何告警！\n"
            f"  可疑关键词: {metadata.matched_patterns}\n"
            f"  ASCII隐写: {metadata.has_ascii_smuggling}\n"
            f"  代码块数: {len(metadata.code_blocks)}"
        )


class TestBenignSamples:
    """正常样本不应触发高危告警"""

    @pytest.mark.parametrize("skill_file", get_benign_files(),
                             ids=lambda f: f.stem)
    def test_benign_low_risk(self, skill_file):
        """正常样本不应有可疑关键词或隐写"""
        metadata = parse_skill_from_file(skill_file)

        # 正常样本不应有隐写
        assert not metadata.has_ascii_smuggling, \
            f"正常样本 {skill_file.name} 误报 ASCII 隐写"

        # 正常样本不应匹配到高危关键词（curl/wget/eval等）
        # 注意：有些正常样本可能包含 eval（如计算器），这里只检查最危险的组合
        dangerous_combos = {"curl", "wget", "bash -c", "id_rsa", "webhook.site"}
        matched_dangerous = set(metadata.matched_patterns) & dangerous_combos
        assert len(matched_dangerous) == 0, \
            f"正常样本 {skill_file.name} 误报危险关键词: {matched_dangerous}"
