"""
二分类评测指标

白话讲解：
- 论文里检测器好不好，靠的是 Precision/Recall/F1/FPR 这几个硬指标，不能拍脑袋。
- 这里约定：正类 = "恶意"(malicious)。
    TP：恶意被判恶意；FP：良性被误判恶意（误报）；
    FN：恶意被漏判良性（漏报）；TN：良性被判良性。
- 所有函数都是纯计算，不依赖数据集，任何地方都能复用（评 baseline，也评我们自己的方法）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ConfusionMatrix(BaseModel):
    """混淆矩阵（正类=恶意）"""
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn


class ClassificationMetrics(BaseModel):
    """一组分类指标 + 其混淆矩阵"""
    precision: float = Field(description="精确率 TP/(TP+FP)")
    recall: float = Field(description="召回率 TP/(TP+FN)")
    f1: float = Field(description="F1 = 2PR/(P+R)")
    fpr: float = Field(description="误报率 FP/(FP+TN)")
    accuracy: float = Field(description="准确率 (TP+TN)/total")
    support_pos: int = Field(description="正类(恶意)样本数")
    support_neg: int = Field(description="负类(良性)样本数")
    confusion: ConfusionMatrix


def _safe_div(numerator: float, denominator: float) -> float:
    """分母为 0 时返回 0，避免除零崩溃。"""
    return numerator / denominator if denominator else 0.0


def confusion_from_labels(
    y_true: list[bool], y_pred: list[bool]
) -> ConfusionMatrix:
    """
    由真值/预测（True=恶意）计算混淆矩阵。

    白话讲解：逐个样本对照"真的是不是恶意"和"我们判成不判成恶意"，累加四格。
    """
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"y_true 与 y_pred 长度不一致：{len(y_true)} vs {len(y_pred)}"
        )
    cm = ConfusionMatrix()
    for truth, pred in zip(y_true, y_pred):
        if truth and pred:
            cm.tp += 1
        elif not truth and pred:
            cm.fp += 1
        elif truth and not pred:
            cm.fn += 1
        else:
            cm.tn += 1
    return cm


def metrics_from_confusion(cm: ConfusionMatrix) -> ClassificationMetrics:
    """由混淆矩阵算出 P/R/F1/FPR/Accuracy。"""
    precision = _safe_div(cm.tp, cm.tp + cm.fp)
    recall = _safe_div(cm.tp, cm.tp + cm.fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    fpr = _safe_div(cm.fp, cm.fp + cm.tn)
    accuracy = _safe_div(cm.tp + cm.tn, cm.total)
    return ClassificationMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        fpr=fpr,
        accuracy=accuracy,
        support_pos=cm.tp + cm.fn,
        support_neg=cm.fp + cm.tn,
        confusion=cm,
    )


def compute_metrics(
    y_true: list[bool], y_pred: list[bool]
) -> ClassificationMetrics:
    """一步到位：由标签直接算全部指标（正类=恶意）。"""
    return metrics_from_confusion(confusion_from_labels(y_true, y_pred))
