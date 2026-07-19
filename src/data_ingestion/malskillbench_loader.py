"""
MalSkillBench 数据集加载器

白话讲解：
- MalSkillBench 是公开的"恶意 Agent 技能"基准数据集（arXiv:2606.07131）。
- 它把技能样本放在两个目录里：
    Dataset/Skills/malware/  —— 恶意技能（3,945 个文件夹）
    Dataset/Skills/benign/   —— 良性技能（4,001 个文件夹，用作误报集）
- 每个技能是一个文件夹，里面有 SKILL.md（说明 + 指令）和 scripts/（可执行代码）。
- 恶意样本的"分类学标签"直接编码在文件夹名字的后缀里，例如：
    muscle-gain__MIXED_B4              → 攻击向量 MIXED，恶意行为 B4
    database-migration__CI_B9__Inline_Code_Block → 向量 CI，行为 B9，插入策略 Inline_Code_Block
    clawhub-xxx__v3.6.1               → 野外样本（后缀是版本号，不是分类标签）
    0x-swap                           → 野外样本（无后缀）

本加载器把这些散落的文件夹解析成统一的 MalSkillSample 结构，供评测框架使用。
注意：数据集本身放在已 gitignore 的 datasets_external/ 下，不入库；恶意样本只在隔离环境执行。
"""
from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field

# 三维分类学的合法取值（与 MalSkillBench README 一致）
# 1) 攻击向量
VALID_VECTORS = {"CI", "PI", "MIXED"}
# 2) 恶意行为 B1-B15（B10-B15 是针对 agent 的控制面攻击，仅 PI）
VALID_BEHAVIORS = {f"B{i}" for i in range(1, 16)}

# 从文件夹名解析分类标签的正则：形如 __<VECTOR>_<BEHAVIOR>[__<INSERTION>]
_LABEL_RE = re.compile(
    r"__(?P<vector>CI|PI|MIXED)_(?P<behavior>B\d{1,2})(?:__(?P<insertion>[A-Za-z0-9_]+))?$"
)

# 数据集默认根目录（可用环境变量 MALSKILLBENCH_ROOT 覆盖）
_DEFAULT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "datasets_external"
    / "MalSkillBench"
)


class MalSkillSample(BaseModel):
    """
    一个 MalSkillBench 技能样本的统一表示

    白话讲解：把"一个技能文件夹"变成一条结构化记录，
    包含标签（是否恶意/三维分类）、路径、SKILL.md 与脚本文件列表。
    """
    skill_id: str = Field(description="技能唯一标识（= 文件夹名）")
    label: str = Field(description="真值标签：malicious / benign")
    split: str = Field(
        description=(
            "标签可得性：benign / malicious_labeled（文件夹名带三维标签）/ "
            "malicious_unlabeled（无标签，多为野外样本）。"
            "注意：这不是官方 generated/wild/test 划分——那需要作者提供的权威索引，"
            "仅凭文件夹名无法可靠还原，故此处只区分‘标签是否可得’。"
        )
    )

    # 三维分类学（仅恶意且为合成样本时有值）
    vector: Optional[str] = Field(default=None, description="攻击向量 CI/PI/MIXED")
    behavior: Optional[str] = Field(default=None, description="恶意行为 B1-B15")
    insertion: Optional[str] = Field(default=None, description="插入策略（可选）")

    # 路径信息
    dir_path: str = Field(description="技能文件夹绝对路径")
    skill_md_path: Optional[str] = Field(default=None, description="SKILL.md 路径（若存在）")
    script_files: list[str] = Field(
        default_factory=list, description="脚本文件绝对路径列表（.py/.sh 等）"
    )

    @property
    def is_agent_control(self) -> bool:
        """
        是否属于"agent 控制面攻击"（B10-B15）——现有检测器最容易崩掉的一类，
        也是本项目方向 A 重点评测的难子集。
        """
        if self.behavior is None:
            return False
        try:
            return int(self.behavior[1:]) >= 10
        except ValueError:
            return False


def parse_folder_label(
    folder_name: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    从技能文件夹名解析三维分类标签。

    返回 (vector, behavior, insertion)；解析不到时对应位置为 None。

    白话讲解：只认 `__CI_B4` / `__PI_B12` / `__MIXED_B6__Download_Execute` 这种规范后缀；
    像 `__v3.6.1`（版本号）或完全没有后缀的野外样本，返回全 None。
    """
    match = _LABEL_RE.search(folder_name)
    if not match:
        return None, None, None

    vector = match.group("vector")
    behavior = match.group("behavior")
    insertion = match.group("insertion")

    # 双保险：行为编号必须在 B1-B15 内，否则视为无效标签
    if behavior not in VALID_BEHAVIORS:
        return None, None, None
    return vector, behavior, insertion


def _collect_scripts(skill_dir: Path) -> list[str]:
    """收集技能文件夹内的可执行脚本文件（递归），返回绝对路径列表。"""
    exts = {".py", ".sh", ".bash", ".js", ".ts", ".rb", ".pl", ".ps1"}
    scripts: list[str] = []
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in exts:
            scripts.append(str(path))
    return scripts


def _build_sample(skill_dir: Path, label: str) -> MalSkillSample:
    """把单个技能文件夹构造成 MalSkillSample。"""
    name = skill_dir.name
    vector, behavior, insertion = parse_folder_label(name)

    if label == "benign":
        split = "benign"
    elif vector is not None:
        # 文件夹名带规范三维标签（可用于分类学子集评测）
        split = "malicious_labeled"
    else:
        # 恶意但文件夹名无三维标签（多为野外样本）
        split = "malicious_unlabeled"

    skill_md = skill_dir / "SKILL.md"
    return MalSkillSample(
        skill_id=name,
        label=label,
        split=split,
        vector=vector,
        behavior=behavior,
        insertion=insertion,
        dir_path=str(skill_dir),
        skill_md_path=str(skill_md) if skill_md.is_file() else None,
        script_files=_collect_scripts(skill_dir),
    )


def get_dataset_root(root: Optional[str | Path] = None) -> Path:
    """
    解析数据集根目录：优先参数，其次环境变量 MALSKILLBENCH_ROOT，最后默认路径。
    """
    if root is not None:
        return Path(root)
    env = os.environ.get("MALSKILLBENCH_ROOT")
    if env:
        return Path(env)
    return _DEFAULT_ROOT


def load_malskillbench(
    root: Optional[str | Path] = None,
    include: tuple[str, ...] = ("malware", "benign"),
    limit: Optional[int] = None,
) -> Iterator[MalSkillSample]:
    """
    遍历 MalSkillBench，逐个产出 MalSkillSample。

    参数：
    - root: 数据集根目录（默认自动定位 datasets_external/MalSkillBench）
    - include: 要加载的子集，("malware",) / ("benign",) / 两者
    - limit: 每个子集最多加载多少个（调试/小批实验用）

    白话讲解：用生成器逐个吐出样本，避免一次性把上万个技能读进内存。
    """
    dataset_root = get_dataset_root(root)
    skills_root = dataset_root / "Dataset" / "Skills"
    if not skills_root.is_dir():
        raise FileNotFoundError(
            f"未找到 MalSkillBench 技能目录：{skills_root}。"
            f"请确认已克隆数据集到 datasets_external/ 或设置 MALSKILLBENCH_ROOT。"
        )

    label_map = {"malware": "malicious", "benign": "benign"}
    for subset in include:
        if subset not in label_map:
            raise ValueError(f"未知子集：{subset}，只支持 malware / benign")
        subset_dir = skills_root / subset
        if not subset_dir.is_dir():
            continue
        count = 0
        for skill_dir in sorted(p for p in subset_dir.iterdir() if p.is_dir()):
            yield _build_sample(skill_dir, label_map[subset])
            count += 1
            if limit is not None and count >= limit:
                break


def read_skill_md(sample: MalSkillSample) -> str:
    """读取样本的 SKILL.md 原始文本（不存在时返回空串）。"""
    if not sample.skill_md_path:
        return ""
    return Path(sample.skill_md_path).read_text(encoding="utf-8", errors="replace")


def read_scripts(sample: MalSkillSample) -> list[tuple[str, str]]:
    """
    读取样本的所有脚本内容。

    返回 [(相对文件名, 文件内容), ...]。
    白话讲解：动态引擎需要真正执行这些脚本，所以要能把代码文本取出来。
    """
    out: list[tuple[str, str]] = []
    base = Path(sample.dir_path)
    for script_path in sample.script_files:
        p = Path(script_path)
        try:
            rel = str(p.relative_to(base))
        except ValueError:
            rel = p.name
        out.append((rel, p.read_text(encoding="utf-8", errors="replace")))
    return out


def dataset_stats(root: Optional[str | Path] = None) -> dict:
    """
    统计数据集分布：总数、标签、划分、向量、行为、控制面占比。

    白话讲解：论文里必须报告数据分布；这个函数一键把统计跑出来，
    也顺便验证加载器解析标签是否正确。
    """
    total = 0
    by_label: Counter[str] = Counter()
    by_split: Counter[str] = Counter()
    by_vector: Counter[str] = Counter()
    by_behavior: Counter[str] = Counter()
    agent_control = 0
    missing_skill_md = 0

    for sample in load_malskillbench(root):
        total += 1
        by_label[sample.label] += 1
        by_split[sample.split] += 1
        if sample.vector:
            by_vector[sample.vector] += 1
        if sample.behavior:
            by_behavior[sample.behavior] += 1
        if sample.is_agent_control:
            agent_control += 1
        if sample.skill_md_path is None:
            missing_skill_md += 1

    return {
        "total": total,
        "by_label": dict(by_label),
        "by_split": dict(by_split),
        "by_vector": dict(by_vector),
        "by_behavior": dict(sorted(by_behavior.items(), key=lambda kv: int(kv[0][1:]))),
        "agent_control_B10_B15": agent_control,
        "missing_skill_md": missing_skill_md,
    }


if __name__ == "__main__":
    # 白话讲解：直接运行本文件即可打印数据集统计，用于快速自检。
    import json

    stats = dataset_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
