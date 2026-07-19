"""
MalSkillBench 数据加载器测试

白话讲解：
- 纯单元测试（parse_folder_label）不依赖真实数据集，任何环境都能跑。
- 集成测试用 skipif 保护：只有本地存在数据集时才跑，避免 CI 因缺数据集而失败。
"""
from pathlib import Path

import pytest

from src.data_ingestion.malskillbench_loader import (
    MalSkillSample,
    dataset_stats,
    get_dataset_root,
    load_malskillbench,
    parse_folder_label,
)

# 判断本地是否存在数据集，用于集成测试的 skip 条件
_DATASET_AVAILABLE = (
    get_dataset_root() / "Dataset" / "Skills"
).is_dir()
_needs_dataset = pytest.mark.skipif(
    not _DATASET_AVAILABLE, reason="本地无 MalSkillBench 数据集，跳过集成测试"
)


class TestParseFolderLabel:
    """三维分类标签解析（纯单元测试）"""

    def test_ci_behavior(self):
        assert parse_folder_label("muscle-gain__CI_B4") == ("CI", "B4", None)

    def test_mixed_with_insertion(self):
        assert parse_folder_label(
            "database-migration__MIXED_B9__Download_Execute"
        ) == ("MIXED", "B9", "Download_Execute")

    def test_pi_agent_control(self):
        assert parse_folder_label("some-skill__PI_B12") == ("PI", "B12", None)

    def test_version_suffix_is_not_label(self):
        # 版本号后缀不是分类标签，应解析为全 None
        assert parse_folder_label("clawhub-xxx__v3.6.1") == (None, None, None)

    def test_no_suffix(self):
        assert parse_folder_label("0x-swap") == (None, None, None)

    def test_out_of_range_behavior(self):
        # B99 不在 B1-B15 范围内，视为无效标签
        assert parse_folder_label("x__CI_B99") == (None, None, None)


class TestIsAgentControl:
    """B10-B15 属于 agent 控制面攻击"""

    def test_b10_is_control(self):
        s = MalSkillSample(
            skill_id="x", label="malicious", split="malicious_labeled",
            vector="PI", behavior="B10", dir_path="/tmp/x",
        )
        assert s.is_agent_control is True

    def test_b9_is_not_control(self):
        s = MalSkillSample(
            skill_id="x", label="malicious", split="malicious_labeled",
            vector="CI", behavior="B9", dir_path="/tmp/x",
        )
        assert s.is_agent_control is False

    def test_none_behavior_is_not_control(self):
        s = MalSkillSample(
            skill_id="x", label="malicious", split="malicious_unlabeled",
            dir_path="/tmp/x",
        )
        assert s.is_agent_control is False


@_needs_dataset
class TestLoadDataset:
    """真实数据集集成测试（本地有数据集时才跑）"""

    def test_load_limit(self):
        samples = list(load_malskillbench(include=("malware",), limit=10))
        assert len(samples) == 10
        assert all(s.label == "malicious" for s in samples)

    def test_benign_label(self):
        samples = list(load_malskillbench(include=("benign",), limit=5))
        assert all(s.label == "benign" and s.split == "benign" for s in samples)

    def test_skill_md_paths_exist(self):
        for s in load_malskillbench(include=("malware",), limit=20):
            if s.skill_md_path is not None:
                assert Path(s.skill_md_path).is_file()

    def test_stats_counts(self):
        stats = dataset_stats()
        # 已核实：3,944 恶意 + 4,000 良性
        assert stats["by_label"]["malicious"] == 3944
        assert stats["by_label"]["benign"] == 4000
        assert stats["total"] == 7944
        # B1-B15 都应出现在带标签的恶意样本里
        assert set(stats["by_behavior"].keys()) <= {f"B{i}" for i in range(1, 16)}
