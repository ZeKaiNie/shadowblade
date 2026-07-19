"""
评测框架测试

白话讲解：
- metrics 的测试是纯计算，任何环境都能跑。
- baseline 表格解析用内置样例字符串测，不依赖真实数据集。
- 真正跑官方脚本的集成测试用 skipif 保护。
"""
import pytest

from src.data_ingestion.malskillbench_loader import get_dataset_root
from src.evaluation.malskillbench_baselines import (
    _parse_table,
    run_official_baselines,
)
from src.evaluation.metrics import (
    ConfusionMatrix,
    compute_metrics,
    confusion_from_labels,
    metrics_from_confusion,
)
from src.evaluation.subset_baselines import compute_subset_recall

_DATASET_AVAILABLE = (get_dataset_root() / "Dataset" / "Skills").is_dir()
_needs_dataset = pytest.mark.skipif(
    not _DATASET_AVAILABLE, reason="本地无 MalSkillBench 数据集，跳过集成测试"
)


class TestMetrics:
    def test_perfect_classifier(self):
        y_true = [True, True, False, False]
        y_pred = [True, True, False, False]
        m = compute_metrics(y_true, y_pred)
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1 == 1.0
        assert m.fpr == 0.0
        assert m.accuracy == 1.0
        assert m.support_pos == 2
        assert m.support_neg == 2

    def test_confusion_counts(self):
        # 真值: 恶,恶,恶,良,良 ; 预测: 恶,良,恶,恶,良
        cm = confusion_from_labels(
            [True, True, True, False, False],
            [True, False, True, True, False],
        )
        assert (cm.tp, cm.fn, cm.fp, cm.tn) == (2, 1, 1, 1)

    def test_metrics_from_confusion(self):
        cm = ConfusionMatrix(tp=2, fp=1, fn=1, tn=1)
        m = metrics_from_confusion(cm)
        assert m.precision == pytest.approx(2 / 3)
        assert m.recall == pytest.approx(2 / 3)
        assert m.f1 == pytest.approx(2 / 3)
        assert m.fpr == pytest.approx(0.5)

    def test_all_negative_predictions_zero_division_safe(self):
        m = compute_metrics([True, False], [False, False])
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1 == 0.0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            confusion_from_labels([True], [True, False])


class TestParseTable:
    def test_parse_official_table(self):
        header = (
            "Tool | TP | FP | TN | FN | Unknown | Missing | InvalidJSON | "
            "Valid | Total | Coverage | Accuracy | Precision | Recall | F1 | FPR | FNR"
        )
        sep = "---+---"
        data = (
            "guarddog | 609 | 49 | 3951 | 3335 | 0 | 0 | 0 | "
            "7944 | 7944 | 1.000000 | 0.574018 | 0.925532 | 0.154412 | "
            "0.264668 | 0.012250 | 0.845588"
        )
        sample = f"{header}\n{sep}\n{data}"
        rows = _parse_table("supplychain", sample)
        assert len(rows) == 1
        r = rows[0]
        assert r.tool == "guarddog"
        assert r.tp == 609 and r.fp == 49
        assert r.precision == pytest.approx(0.925532)
        assert r.recall == pytest.approx(0.154412)
        assert r.f1 == pytest.approx(0.264668)

    def test_header_and_separator_skipped(self):
        rows = _parse_table("x", "Tool | TP\n---+---\n")
        assert rows == []


@_needs_dataset
class TestRunOfficialBaselines:
    def test_supplychain_guarddog_present(self):
        rows = run_official_baselines(families=("supplychain",))
        tools = {r.tool for r in rows}
        assert "guarddog" in tools
        # guarddog 高精度低召回是已知特征
        gd = next(r for r in rows if r.tool == "guarddog")
        assert gd.precision > 0.8
        assert gd.recall < 0.3


@_needs_dataset
class TestSubsetRecall:
    def test_control_plane_subset(self):
        rows = compute_subset_recall(tools=("virustotal", "AI-Infra-Guard"))
        # 每个工具应产出 全量 + 控制面 两条
        subsets = {(r.tool, r.subset) for r in rows}
        assert ("virustotal", "malicious_all") in subsets
        assert ("virustotal", "agent_control_B10_15") in subsets
        # 控制面子集恰为 B10–B15，共 259 个（与数据加载器统计一致）
        vt_ac = next(
            r for r in rows
            if r.tool == "virustotal" and r.subset == "agent_control_B10_15"
        )
        assert vt_ac.total == 259
        # virustotal 对控制面攻击几乎完全漏检
        assert vt_ac.recall < 0.05
