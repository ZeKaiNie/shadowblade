"""混合级联检测器单元测试（不依赖 Docker 或外部数据集）。"""

from types import SimpleNamespace

import pytest

from src.cascade.cascade import run_cascade
from src.cascade.evaluate import budget_curve, cascade_metrics


def _stage2_report(decision: str, executed: bool, honeypot: bool = False):
    """构造足够覆盖级联逻辑的轻量运行时报告。"""

    conformance = SimpleNamespace(
        deviation_score=0.8 if decision != "allow" else 0.0,
        honeypot_triggered=honeypot,
    )
    return SimpleNamespace(
        decision=decision,
        executed=executed,
        conformance=conformance,
    )


def test_low_stage1_risk_skips_stage2():
    """Stage-1 不报时应直接放行，且绝不能调用 Stage-2。"""

    called = False

    def stage2(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("不应调用 Stage-2")

    result = run_cascade(
        "说明",
        ["print('ok')"],
        stage1_fn=lambda _markdown: SimpleNamespace(risk_score=0.1),
        stage2_fn=stage2,
    )

    assert result.final_decision == "allow"
    assert result.final_flag is False
    assert result.stage2_outcome == "skipped"
    assert result.stage2_ran is False
    assert called is False


def test_stage2_confirmed_deny_with_honeypot():
    """运行时 deny 且蜜罐命中时，级联应确认告警。"""

    result = run_cascade(
        "说明",
        ["print('bad')"],
        stage1_fn=lambda _markdown: SimpleNamespace(risk_score=0.7),
        stage2_fn=lambda **_kwargs: _stage2_report("deny", True, True),
    )

    assert result.final_decision == "deny"
    assert result.final_flag is True
    assert result.stage2_outcome == "confirmed"
    assert result.honeypot_triggered is True


def test_stage2_refuted_prunes_static_alert():
    """沙箱真实执行且干净时，Stage-1 告警应被剪枝。"""

    result = run_cascade(
        "说明",
        ["print('ok')"],
        stage1_fn=lambda _markdown: SimpleNamespace(risk_score=0.5),
        stage2_fn=lambda **_kwargs: _stage2_report("allow", True),
    )

    assert result.final_decision == "allow"
    assert result.final_flag is False
    assert result.stage2_outcome == "refuted"


def test_stage2_abstained_keeps_review_alert():
    """沙箱未执行时不能剪枝，只能把候选告警保留为 review。"""

    result = run_cascade(
        "说明",
        ["not valid python"],
        stage1_fn=lambda _markdown: SimpleNamespace(risk_score=0.5),
        stage2_fn=lambda **_kwargs: _stage2_report("allow", False),
    )

    assert result.final_decision == "review"
    assert result.final_flag is True
    assert result.stage2_outcome == "abstained"


def test_non_gate_runs_stage2_even_when_stage1_does_not_flag():
    """非门控模式不能因静态低风险而跳过运行时确认。"""

    called = False

    def stage2(**_kwargs):
        nonlocal called
        called = True
        return _stage2_report("deny", True, True)

    result = run_cascade(
        "说明",
        ["print('bad')"],
        stage1_fn=lambda _markdown: SimpleNamespace(risk_score=0.1),
        stage2_fn=stage2,
        gate=False,
    )

    assert called is True
    assert result.stage1_flag is False
    assert result.stage2_ran is True
    assert result.stage2_outcome == "always_run"
    assert result.final_decision == "deny"
    assert result.final_flag is True


def test_stage1_receives_appended_code_blocks_and_stage2_arguments():
    """独立脚本必须追加进 Stage-1 Markdown，蜜罐等参数需透传给 Stage-2。"""

    seen_markdown = []
    seen_kwargs = {}

    def stage1(markdown):
        seen_markdown.append(markdown)
        return SimpleNamespace(risk_score=0.5)

    def stage2(**kwargs):
        seen_kwargs.update(kwargs)
        return _stage2_report("allow", True)

    honeypot = object()
    run_cascade(
        "正文",
        ["print(1)"],
        code_languages=["python"],
        backend="fake",
        timeout=7,
        honeypot=honeypot,
        stage1_fn=stage1,
        stage2_fn=stage2,
    )

    assert "```python\nprint(1)\n```" in seen_markdown[0]
    assert seen_kwargs["honeypot"] is honeypot
    assert seen_kwargs["backend"] == "fake"
    assert seen_kwargs["timeout"] == 7


def test_cascade_metrics_baselines_and_strata():
    """三套指标、良性 FP 剪枝数和向量分层计数应与手算一致。"""

    records = [
        {
            "label": "malicious",
            "vector": "CI",
            "stage1_flag": True,
            "stage2_only_flag": True,
            "final_flag": True,
            "stage2_executed": True,
            "stage2_outcome": "confirmed",
        },
        {
            "label": "benign",
            "vector": "CI",
            "stage1_flag": True,
            "stage2_only_flag": False,
            "final_flag": False,
            "stage2_executed": True,
            "stage2_outcome": "refuted",
        },
        {
            "label": "malicious",
            "vector": "PI",
            "stage1_flag": False,
            "stage2_only_flag": True,
            "final_flag": False,
            "stage2_executed": False,
            "stage2_outcome": "skipped",
        },
        {
            "label": "benign",
            "vector": None,
            "stage1_flag": False,
            "stage2_only_flag": False,
            "final_flag": False,
            "stage2_executed": False,
            "stage2_outcome": "skipped",
        },
    ]

    result = cascade_metrics(records)

    assert result["stage1_only"]["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert result["stage2_only"]["confusion"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 2}
    assert result["cascade"]["confusion"] == {"tp": 1, "fp": 0, "fn": 1, "tn": 2}
    assert result["strata"]["CI"]["confirmed"] == 1
    assert result["strata"]["CI"]["refuted"] == 1
    assert result["strata"]["PI"]["stage1_flagged"] == 0
    assert result["strata"]["wild"]["benign"] == 1
    assert result["false_positive_reduction"]["stage1_benign_fp"] == 1
    assert result["false_positive_reduction"]["refuted_benign_fp"] == 1
    assert result["false_positive_reduction"]["reduction_rate"] == pytest.approx(1.0)
    assert result["recall_change"]["absolute_change"] == pytest.approx(0.0)


def test_budget_curve_uses_stage1_priority_and_matches_stage2_at_full_budget():
    """预算为 100% 时应等于 Stage-2-only，低预算优先选高风险样本。"""

    records = [
        {
            "label": "malicious",
            "stage1_risk": 0.9,
            "stage2_only_flag": True,
        },
        {
            "label": "benign",
            "stage1_risk": 0.8,
            "stage2_only_flag": False,
        },
        {
            "label": "malicious",
            "stage1_risk": 0.2,
            "stage2_only_flag": True,
        },
        {
            "label": "benign",
            "stage1_risk": 0.1,
            "stage2_only_flag": False,
        },
    ]

    result = budget_curve(records, budgets=(0.25, 1.0), n_random_trials=200)
    low_budget = result["budgets"][0]
    full_budget = result["budgets"][1]

    assert low_budget["n_selected"] == 1
    assert low_budget["stage1_priority"]["detected_malicious"] == 1
    assert low_budget["stage1_priority"]["recall"] == pytest.approx(0.5)
    assert full_budget["stage1_priority"]["recall"] == pytest.approx(1.0)
    assert full_budget["stage1_priority"]["fpr"] == pytest.approx(0.0)
    assert full_budget["stage1_priority"]["detected_malicious"] == 2
    assert full_budget["random"]["recall"] == pytest.approx(1.0)
    assert full_budget["random"]["fpr"] == pytest.approx(0.0)
