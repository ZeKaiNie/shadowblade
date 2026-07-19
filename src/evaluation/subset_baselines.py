"""
按攻击子集统计 baseline 召回率（重点：agent 控制面 B10–B15）

白话讲解：
- MalSkillBench 原文的核心结论之一：检测器对代码注入召回很高，但对
  提示词注入 / agent 控制面攻击"召回崩塌"。这是方向 A 主攻的靶子。
- 官方汇总脚本只出"全量"指标；本模块**复用官方脚本里每个工具自己的 parser**
  （不自造解析逻辑），把逐样本预测按"行为子集"过滤，算**子集召回率**。
- 为什么只算召回：B10–B15 子集里全是恶意样本（没有对应良性），
  精确率/FPR 需要负样本才有意义，故此处只报召回（= 检出率），
  用"全量恶意召回 vs 控制面 B10–B15 召回"的对比来量化"崩塌"。

来源声明：逐样本预测与 parser 均来自 MalSkillBench(arXiv:2606.07131) 官方结果与脚本，
本模块只做子集过滤与召回统计，引用须标注来源。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

from pydantic import BaseModel

from src.data_ingestion.malskillbench_loader import get_dataset_root, parse_folder_label

# 复用 RQ3(skillsecurity) 官方脚本里各工具的 parser。
# 每项：显示名 -> (结果子目录, 从 result.json payload 取预测的函数)
_ToolParser = Callable[[dict], Optional[bool]]


class SubsetRecall(BaseModel):
    """单个工具在某子集上的召回统计"""
    tool: str
    subset: str
    detected: int
    total: int
    unknown: int

    @property
    def recall(self) -> float:
        return self.detected / self.total if self.total else 0.0


def _load_rq3_module(root: Path) -> ModuleType:
    """按路径动态加载 RQ3 官方脚本，拿到它的 parser 函数。"""
    script = root / "Experiment" / "RQ3" / "baseline_accuracy.py"
    if not script.is_file():
        raise FileNotFoundError(f"未找到 RQ3 官方脚本：{script}")
    spec = importlib.util.spec_from_file_location("_msb_rq3", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载脚本：{script}")
    module = importlib.util.module_from_spec(spec)
    # 官方脚本里用了 @dataclass，其内省需要模块已注册进 sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_registry(mod: ModuleType) -> dict[str, tuple[str, _ToolParser]]:
    """构造 显示名 -> (结果子目录, parser) 注册表，parser 直接复用官方实现。"""
    return {
        "AI-Infra-Guard": (
            "AI-Infra-Guard",
            lambda p: mod.parse_ai_infra_guard_report(p.get("report")),
        ),
        "getsentry-skill-scanner--full": (
            "getsentry-skill-scanner--full",
            mod.parse_getsentry_full_report,
        ),
        "cisco-skill-scanner--llm": (
            "cisco-skill-scanner--llm",
            mod.parse_cisco_skill_scanner_report,
        ),
        "snyk-agent-scan": ("snyk-agent-scan", mod.parse_snyk_agent_scan_report),
        "llm-guard": ("llm-guard", mod.parse_llm_guard_report),
        "virustotal": ("virustotal", mod.parse_virustotal_report),
    }


def _is_agent_control(skill_name: str) -> bool:
    """B10–B15 视为 agent 控制面攻击。"""
    _, behavior, _ = parse_folder_label(skill_name)
    if behavior is None:
        return False
    try:
        return int(behavior[1:]) >= 10
    except ValueError:
        return False


def compute_subset_recall(
    root: Optional[str | Path] = None,
    tools: Optional[tuple[str, ...]] = None,
) -> list[SubsetRecall]:
    """
    为每个工具计算：全量恶意召回 vs agent 控制面(B10–B15) 召回。

    白话讲解：只遍历 malware 目录（全是恶意），对每个技能用官方 parser 取预测，
    分别累计"全量"和"控制面子集"的检出。
    """
    dataset_root = get_dataset_root(root)
    mod = _load_rq3_module(dataset_root)
    registry = _build_registry(mod)
    tools = tools or tuple(registry.keys())

    malware_dir = dataset_root / "Dataset" / "Skills" / "malware"
    skill_names = sorted(p.name for p in malware_dir.iterdir() if p.is_dir())

    out: list[SubsetRecall] = []
    for tool in tools:
        subdir, parser = registry[tool]
        result_root = dataset_root / "Experiment" / "Results" / "skillsecurity" / subdir

        stats = {
            "malicious_all": {"detected": 0, "total": 0, "unknown": 0},
            "agent_control_B10_15": {"detected": 0, "total": 0, "unknown": 0},
        }
        for skill_name in skill_names:
            result_file = result_root / "malware" / skill_name / "result.json"
            predicted: Optional[bool]
            if not result_file.exists():
                predicted = None
            else:
                try:
                    payload = json.loads(result_file.read_text(encoding="utf-8"))
                    predicted = parser(payload) if isinstance(payload, dict) else None
                except (json.JSONDecodeError, OSError):
                    predicted = None

            buckets = ["malicious_all"]
            if _is_agent_control(skill_name):
                buckets.append("agent_control_B10_15")
            for bucket in buckets:
                stats[bucket]["total"] += 1
                if predicted is None:
                    stats[bucket]["unknown"] += 1
                elif predicted:
                    stats[bucket]["detected"] += 1

        for subset, s in stats.items():
            out.append(
                SubsetRecall(
                    tool=tool, subset=subset,
                    detected=s["detected"], total=s["total"], unknown=s["unknown"],
                )
            )
    return out


def format_subset_markdown(rows: list[SubsetRecall]) -> str:
    """把子集召回格式化成 Markdown（全量 vs 控制面并列，便于看崩塌）。"""
    by_tool: dict[str, dict[str, SubsetRecall]] = {}
    for r in rows:
        by_tool.setdefault(r.tool, {})[r.subset] = r
    header = (
        "| 工具 | 全量恶意召回 | 控制面(B10–B15)召回 | 召回下降 |\n"
        "|---|---|---|---|\n"
    )
    lines = []
    for tool, d in by_tool.items():
        all_r = d.get("malicious_all")
        ac_r = d.get("agent_control_B10_15")
        if all_r is None or ac_r is None:
            continue
        drop = all_r.recall - ac_r.recall
        lines.append(
            f"| {tool} | {all_r.recall:.3f} ({all_r.detected}/{all_r.total}) | "
            f"{ac_r.recall:.3f} ({ac_r.detected}/{ac_r.total}) | {drop:+.3f} |"
        )
    return header + "\n".join(lines)


if __name__ == "__main__":
    subset_rows = compute_subset_recall()
    print(format_subset_markdown(subset_rows))
