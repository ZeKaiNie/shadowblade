"""
方向 A 小批端到端评测（真实 MalSkillBench 样本）

白话讲解：
- 从 MalSkillBench 采样 N 个恶意 + N 个良性技能（**只取含 Python 脚本的样本**，
  因为运行时接地核验需要真跑代码；无脚本的 PI 类样本走静态/LLM 路径，不在本小批内）。
- 每个样本：读 SKILL.md 抽声明能力 → 把脚本丢进隔离 Docker 沙箱(带蜜罐, --network none)真跑
  → 观测能力 → 一致性核验 → 决策(allow/review/deny)。
- 判定规则：decision != 'allow' 视为"标记为可疑/恶意"(flagged)。
- 汇总 TP/FP/TN/FN + P/R/F1/FPR，并统计决策分布、蜜罐命中数、执行成功率、平均耗时。

⚠️ 安全：真实恶意代码只在 Docker(--network none, 内存/PID 限制, 临时工作区)内执行，绝不在宿主运行。
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from src.conformance.pipeline import verify_skill_from_code
from src.data_ingestion.malskillbench_loader import (
    MalSkillSample,
    load_malskillbench,
    read_scripts,
    read_skill_md,
)
from src.evaluation.metrics import compute_metrics


def _collect_with_scripts(label_subset: str, cap: int) -> list[MalSkillSample]:
    """收集含 Python 脚本的样本（cap 为上限，避免遍历全量）。"""
    out: list[MalSkillSample] = []
    for sample in load_malskillbench(include=(label_subset,)):
        if sample.script_files:
            out.append(sample)
            if len(out) >= cap:
                break
    return out


def _run_one(sample: MalSkillSample, timeout: int) -> dict:
    """对单个样本跑完整管线，返回结构化记录。"""
    skill_md = read_skill_md(sample)
    scripts = read_scripts(sample)
    code_blocks = [content for _, content in scripts]
    languages = ["python"] * len(code_blocks)

    t0 = time.time()
    report = verify_skill_from_code(
        skill_md_text=skill_md,
        code_blocks=code_blocks,
        code_languages=languages,
        backend="docker",
        timeout=timeout,
    )
    elapsed = time.time() - t0

    c = report.conformance
    return {
        "skill_id": sample.skill_id,
        "label": sample.label,
        "vector": sample.vector,
        "behavior": sample.behavior,
        "is_agent_control": sample.is_agent_control,
        "executed": report.executed,
        "backend": report.backend,
        "dynamic_risk": report.dynamic_risk,
        "declared": c.declared,
        "observed": c.observed,
        "undeclared_sensitive": c.undeclared_sensitive,
        "honeypot_triggered": c.honeypot_triggered,
        "deviation_score": c.deviation_score,
        "decision": report.decision,
        "elapsed_sec": round(elapsed, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="方向 A 小批端到端评测")
    parser.add_argument("--n", type=int, default=50, help="每类样本数（恶意/良性各 n）")
    parser.add_argument("--seed", type=int, default=20260718, help="随机种子")
    parser.add_argument("--timeout", type=int, default=30, help="单样本沙箱超时(秒)")
    parser.add_argument("--pool", type=int, default=400, help="候选池上限(含脚本样本)")
    parser.add_argument(
        "--out", type=str, default="runs/pilot_batch.json", help="结果输出路径"
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    mal_pool = _collect_with_scripts("malware", args.pool)
    ben_pool = _collect_with_scripts("benign", args.pool)
    print(f"候选池：malware(with py)={len(mal_pool)} benign(with py)={len(ben_pool)}")

    mal = rng.sample(mal_pool, min(args.n, len(mal_pool)))
    ben = rng.sample(ben_pool, min(args.n, len(ben_pool)))
    samples = mal + ben
    rng.shuffle(samples)
    print(f"本批：malware={len(mal)} benign={len(ben)} total={len(samples)}")

    records: list[dict] = []
    for i, sample in enumerate(samples, 1):
        rec = _run_one(sample, args.timeout)
        records.append(rec)
        print(
            f"[{i}/{len(samples)}] {rec['label']:9s} "
            f"exec={rec['executed']} risk={rec['dynamic_risk']:.2f} "
            f"honeypot={rec['honeypot_triggered']} decision={rec['decision']} "
            f"({rec['elapsed_sec']}s) {rec['skill_id'][:48]}"
        )

    # 指标：正类=malicious；flagged = decision != allow
    y_true = [r["label"] == "malicious" for r in records]
    y_pred = [r["decision"] != "allow" for r in records]
    metrics = compute_metrics(y_true, y_pred)

    executed = sum(r["executed"] for r in records)
    honeypots = sum(r["honeypot_triggered"] for r in records)
    decisions: dict[str, int] = {}
    for r in records:
        decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1
    avg_elapsed = sum(r["elapsed_sec"] for r in records) / max(len(records), 1)

    summary = {
        "config": vars(args),
        "n_total": len(records),
        "executed": executed,
        "honeypot_hits": honeypots,
        "decision_distribution": decisions,
        "avg_elapsed_sec": round(avg_elapsed, 2),
        "metrics": metrics.model_dump(),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n===== SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n结果已写入：{out_path}")


if __name__ == "__main__":
    main()
