"""
复现 MalSkillBench 自带 baseline 的对照指标

白话讲解：
- MalSkillBench 仓库自带每个 baseline 工具的逐样本预测（Experiment/Results/），
  以及三个官方汇总脚本（RQ3/RQ4 下的 *_baseline_accuracy.py），能算出论文里的 P/R/F1/FPR。
- 不同工具的 result.json 字段五花八门（guarddog 看 issues、llm-guard 看 verdict、
  prompt-guard-2 看 is_injection …），逐个手写解析既易错又不诚实。
- 因此本模块**直接调用 MalSkillBench 官方汇总脚本**，解析其输出表格，得到权威对照数字。
  这样每个工具的判定逻辑用作者自己的实现，我们只做"跑脚本 + 读表格"，并注明来源。

引用声明：这些数字来自 MalSkillBench(arXiv:2606.07131) 官方脚本在本地数据上的运行结果，
论文中引用时须标注来源，不得据为己有。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from src.data_ingestion.malskillbench_loader import get_dataset_root

# 三个官方汇总脚本（相对数据集根）
_OFFICIAL_SCRIPTS = {
    "supplychain": Path("Experiment") / "RQ4" / "supplychain_baseline_accuracy.py",
    "promptinjection": Path("Experiment") / "RQ4" / "promptinjection_baseline_accuracy.py",
    "skillsecurity": Path("Experiment") / "RQ3" / "baseline_accuracy.py",
}

# 官方表格的列顺序
_COLUMNS = [
    "tool", "tp", "fp", "tn", "fn", "unknown", "missing", "invalid_json",
    "valid", "total", "coverage", "accuracy", "precision", "recall",
    "f1", "fpr", "fnr",
]
_INT_COLS = {"tp", "fp", "tn", "fn", "unknown", "missing", "invalid_json", "valid", "total"}


class BaselineRow(BaseModel):
    """单个 baseline 工具的对照指标（来自 MalSkillBench 官方脚本）"""
    family: str
    tool: str
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    f1: float
    fpr: float
    accuracy: float


def _parse_table(family: str, stdout: str) -> list[BaselineRow]:
    """把官方脚本打印的竖线分隔表格解析成 BaselineRow 列表。"""
    rows: list[BaselineRow] = []
    for line in stdout.splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        # 跳过表头与分隔线
        if not cells or cells[0].lower() == "tool" or set(cells[0]) <= {"-", "+", ""}:
            continue
        if len(cells) < len(_COLUMNS):
            continue
        record: dict = {"family": family}
        try:
            for key, raw in zip(_COLUMNS, cells):
                if key == "tool":
                    record[key] = raw
                elif key in _INT_COLS:
                    record[key] = int(raw)
                else:
                    record[key] = float(raw)
        except ValueError:
            continue
        rows.append(
            BaselineRow(
                family=family,
                tool=record["tool"],
                tp=record["tp"], fp=record["fp"], tn=record["tn"], fn=record["fn"],
                precision=record["precision"], recall=record["recall"],
                f1=record["f1"], fpr=record["fpr"], accuracy=record["accuracy"],
            )
        )
    return rows


def run_official_baselines(
    families: Optional[tuple[str, ...]] = None,
    root: Optional[str | Path] = None,
) -> list[BaselineRow]:
    """
    运行 MalSkillBench 官方汇总脚本，返回所有 baseline 的对照指标。

    白话讲解：对每个大类跑一次官方脚本，把表格解析成结构化记录。
    families 默认三类全跑；root 默认自动定位数据集。
    """
    dataset_root = get_dataset_root(root)
    families = families or tuple(_OFFICIAL_SCRIPTS.keys())
    out: list[BaselineRow] = []
    for family in families:
        script = dataset_root / _OFFICIAL_SCRIPTS[family]
        if not script.is_file():
            continue
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, cwd=str(dataset_root),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"官方 baseline 脚本运行失败：{script}\n{proc.stderr[:500]}"
            )
        out.extend(_parse_table(family, proc.stdout))
    return out


def format_markdown_table(rows: list[BaselineRow]) -> str:
    """把 baseline 指标格式化成 Markdown 表格（写入文档用）。"""
    header = (
        "| 类别 | 工具 | Precision | Recall | F1 | FPR | Accuracy |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    body = "\n".join(
        f"| {r.family} | {r.tool} | {r.precision:.3f} | {r.recall:.3f} | "
        f"{r.f1:.3f} | {r.fpr:.3f} | {r.accuracy:.3f} |"
        for r in rows
    )
    return header + body


if __name__ == "__main__":
    baseline_rows = run_official_baselines()
    print(format_markdown_table(baseline_rows))
