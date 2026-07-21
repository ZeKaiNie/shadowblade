"""混合级联检测器的纯评测函数。"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from src.evaluation.metrics import compute_metrics


def _metric_dump(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    """把 Pydantic 指标转成可直接 JSON 序列化的字典。"""

    return compute_metrics(y_true, y_pred).model_dump()


def cascade_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    同时计算两级基线、级联结果、向量分层统计和误报/召回变化。

    ``records`` 是刻意保持宽松的普通字典，方便批处理脚本增补实验字段。
    """

    y_true = [record["label"] == "malicious" for record in records]
    stage1_pred = [bool(record["stage1_flag"]) for record in records]
    stage2_pred = [bool(record["stage2_only_flag"]) for record in records]
    cascade_pred = [bool(record["final_flag"]) for record in records]
    stage1_metrics = _metric_dump(y_true, stage1_pred)
    cascade_result = _metric_dump(y_true, cascade_pred)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record.get("vector") or "wild"].append(record)
    strata: dict[str, dict[str, Any]] = {}
    for vector, group in sorted(grouped.items()):
        outcomes = [record.get("stage2_outcome", "skipped") for record in group]
        strata[vector] = {
            "total": len(group),
            "malicious": sum(r["label"] == "malicious" for r in group),
            "benign": sum(r["label"] == "benign" for r in group),
            "stage1_flagged": sum(bool(r["stage1_flag"]) for r in group),
            "cascade_flagged": sum(bool(r["final_flag"]) for r in group),
            "stage2_executed": sum(bool(r.get("stage2_executed", False)) for r in group),
            "confirmed": outcomes.count("confirmed"),
            "refuted": outcomes.count("refuted"),
            "abstained": outcomes.count("abstained"),
            "skipped": outcomes.count("skipped"),
            "always_run": outcomes.count("always_run"),
        }

    benign_fp = sum(
        record["label"] == "benign" and bool(record["stage1_flag"])
        for record in records
    )
    refuted_benign_fp = sum(
        record["label"] == "benign"
        and bool(record["stage1_flag"])
        and record.get("stage2_outcome") == "refuted"
        for record in records
    )
    reduction_rate = refuted_benign_fp / benign_fp if benign_fp else 0.0
    stage1_recall = stage1_metrics["recall"]
    cascade_recall = cascade_result["recall"]

    return {
        "stage1_only": stage1_metrics,
        "stage2_only": _metric_dump(y_true, stage2_pred),
        "cascade": cascade_result,
        "strata": strata,
        "false_positive_reduction": {
            "stage1_benign_fp": benign_fp,
            "refuted_benign_fp": refuted_benign_fp,
            "reduction_rate": reduction_rate,
        },
        "recall_change": {
            "stage1": stage1_recall,
            "cascade": cascade_recall,
            "absolute_change": cascade_recall - stage1_recall,
        },
    }


def _budget_count(budget: float, sample_count: int) -> int:
    """把 0-1 的预算比例换成样本数，遵循题目要求的 round(B*N)。"""

    if not 0.0 <= budget <= 1.0:
        raise ValueError("预算比例必须在 0 到 1 之间")
    return round(budget * sample_count)


def _budget_metrics(
    records: list[dict[str, Any]], selected: set[int]
) -> dict[str, float | int]:
    """计算一次预算选择对应的召回、误报率和检出恶意数。"""

    y_true = [record["label"] == "malicious" for record in records]
    y_pred = [
        bool(record["stage2_only_flag"]) if index in selected else False
        for index, record in enumerate(records)
    ]
    metrics = compute_metrics(y_true, y_pred)
    return {
        "recall": metrics.recall,
        "fpr": metrics.fpr,
        "detected_malicious": sum(truth and pred for truth, pred in zip(y_true, y_pred)),
    }


def budget_curve(
    records: list[dict[str, Any]],
    budgets: tuple[float, ...] = tuple(i / 10 for i in range(1, 11)),
    n_random_trials: int = 1000,
    seed: int = 20260718,
) -> dict[str, Any]:
    """
    比较 Stage-1 风险排序分诊与随机分诊在有限 Stage-2 预算下的效果。

    未被预算选中的样本按 allow 处理；被选中的样本采用其
    ``stage2_only_flag``。随机基线使用固定种子，保证曲线可复现。
    """

    if not records:
        raise ValueError("records 不能为空")
    if n_random_trials <= 0:
        raise ValueError("n_random_trials 必须为正数")

    sample_count = len(records)
    priority_order = sorted(
        range(sample_count),
        key=lambda index: (-float(records[index]["stage1_risk"]), index),
    )
    rng = random.Random(seed)
    curve: list[dict[str, Any]] = []

    for budget in budgets:
        count = _budget_count(float(budget), sample_count)
        priority_selected = set(priority_order[:count])
        priority_metrics = _budget_metrics(records, priority_selected)

        random_recalls: list[float] = []
        random_fprs: list[float] = []
        random_detected: list[int] = []
        for _ in range(n_random_trials):
            random_selected = set(rng.sample(range(sample_count), count))
            trial = _budget_metrics(records, random_selected)
            random_recalls.append(float(trial["recall"]))
            random_fprs.append(float(trial["fpr"]))
            random_detected.append(int(trial["detected_malicious"]))

        curve.append(
            {
                "budget": float(budget),
                "n_selected": count,
                "stage1_priority": priority_metrics,
                "random": {
                    "recall": sum(random_recalls) / n_random_trials,
                    "fpr": sum(random_fprs) / n_random_trials,
                    "detected_malicious": sum(random_detected) / n_random_trials,
                },
            }
        )

    return {
        "budgets": curve,
        "n_records": sample_count,
        "n_random_trials": n_random_trials,
        "seed": seed,
    }
