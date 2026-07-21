"""
混合级联检测器批量评测（真实数据集执行脚本）。

注意：本脚本会在隔离 Docker 内执行真实恶意代码，必须确保 Docker 可用。
数据集缺失时会报错退出；脚本不会伪造样本或实验结果。
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from src.cascade.cascade import run_cascade
from src.cascade.evaluate import cascade_metrics
from src.conformance.pipeline import verify_skill_from_code
from src.data_ingestion.malskillbench_loader import (
    MalSkillSample,
    load_malskillbench,
    read_scripts,
    read_skill_md,
)


def _collect_with_scripts(label_subset: str, cap: int) -> list[MalSkillSample]:
    """收集至少含一个 Python 脚本的样本，避免把不可执行样本混入本批。"""

    out: list[MalSkillSample] = []
    for sample in load_malskillbench(include=(label_subset,)):
        if any(Path(path).suffix.lower() == ".py" for path in sample.script_files):
            out.append(sample)
            if len(out) >= cap:
                break
    return out


def _run_one(sample: MalSkillSample, timeout: int, stage1_threshold: float) -> dict:
    """对一个样本运行级联，并补齐 Stage-2-only 全量基线。"""

    skill_md = read_skill_md(sample)
    scripts = read_scripts(sample)
    code_blocks = [content for _, content in scripts]
    languages = ["python"] * len(code_blocks)

    started = time.time()
    cascade = run_cascade(
        skill_md_text=skill_md,
        code_blocks=code_blocks,
        code_languages=languages,
        stage1_threshold=stage1_threshold,
        backend="docker",
        timeout=timeout,
    )

    # 候选样本在级联中已经执行过 Stage-2，直接复用结果，避免重复启动 Docker。
    if cascade.stage2_ran:
        stage2_only_flag = cascade.stage2_decision != "allow"
    else:
        baseline = verify_skill_from_code(
            skill_md_text=skill_md,
            code_blocks=code_blocks,
            code_languages=languages,
            backend="docker",
            timeout=timeout,
        )
        stage2_only_flag = baseline.decision != "allow"

    return {
        "skill_id": sample.skill_id,
        "label": sample.label,
        "vector": sample.vector or "wild",
        "behavior": sample.behavior,
        "stage1_risk": cascade.stage1_risk,
        "stage1_flag": cascade.stage1_flag,
        "stage2_only_flag": stage2_only_flag,
        "stage2_ran": cascade.stage2_ran,
        "stage2_executed": cascade.stage2_executed,
        "stage2_decision": cascade.stage2_decision,
        "stage2_deviation": cascade.stage2_deviation,
        "honeypot_triggered": cascade.honeypot_triggered,
        "stage2_outcome": cascade.stage2_outcome,
        "final_decision": cascade.final_decision,
        "final_flag": cascade.final_flag,
        "reasons": cascade.reasons,
        "elapsed_sec": round(time.time() - started, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="混合级联检测器 MalSkillBench 小批评测")
    parser.add_argument("--n", type=int, default=50, help="每类样本数（恶意/良性各 n）")
    parser.add_argument("--seed", type=int, default=20260718, help="随机种子")
    parser.add_argument("--timeout", type=int, default=30, help="单样本沙箱超时(秒)")
    parser.add_argument("--pool", type=int, default=400, help="候选池上限")
    parser.add_argument("--stage1-threshold", type=float, default=0.2, help="Stage-1 候选阈值")
    parser.add_argument("--out", type=str, default="runs/cascade50.json", help="结果输出路径")
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
    for index, sample in enumerate(samples, 1):
        record = _run_one(sample, args.timeout, args.stage1_threshold)
        records.append(record)
        print(
            f"[{index}/{len(samples)}] {record['label']:9s} "
            f"s1={record['stage1_risk']:.2f} outcome={record['stage2_outcome']} "
            f"final={record['final_decision']} ({record['elapsed_sec']}s) "
            f"{record['skill_id'][:48]}"
        )

    summary = {
        "config": vars(args),
        "n_total": len(records),
        "metrics": cascade_metrics(records),
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
