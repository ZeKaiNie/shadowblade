"""混合级联检测器的纯评测函数。"""

from __future__ import annotations

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
