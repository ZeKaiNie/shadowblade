# 方向 A 研究计划：运行时接地的技能能力一致性核验、蜜罐取证与阻断

> 状态：草案 v1（2026-07，已联网核实竞品 + 已本地拉取公开数据集验证可用）
> 定位目标：中文核心（《信息安全学报》/《网络与信息安全学报》）为主 + arXiv preprint 占位
> + CCF-C 会议冲刺。**不**以 CCF-A/B、SCI Q1 为目标。
> 学术诚信：本文所有引用的竞品/数据均已联网核实（见 `2026现状调研与论文方向修正.md`）；
> 任何实验数字必须真实跑出，未跑出前不写入。

---

## 1. 问题与缝隙（已核实）

Agent skills（`SKILL.md` + 脚本 + 权限声明）是"代码 + 面向 agent 的自然语言指令"的混合体，
形成新型供应链攻击面。2026 年已有多篇预印本/论文占据主要方向：

- **USENIX Sec'26《Do Not Mention This to the User》**(arXiv 2602.06547)：爬虫→静态→
  Docker 沙箱行为验证→LLM 研判；数据集 98,380 技能 / 157 确认恶意（已开源）。
- **MalSkillBench**(arXiv 2606.07131)：运行时验证基准，3,944 恶意 + 4,000 良性，108 格三维分类学，
  Docker 沙箱 + 系统调用监控 + LLM judge（已开源全套数据 + baseline + 实验）。
- **BIV**(arXiv 2605.11770)：声明能力 vs 实际能力的"行为完整性核验"，但**实际能力是静态预测**、
  **不做运行时执行、不做蜜罐、不做阻断**。

**MalSkillBench 明确的开放问题**：最强检测器对**代码注入**recall 98.4%，但对**提示词注入(PI)
和 agent 控制面攻击(B10–B15)崩掉**；"检测必须联合推理 意图 + 代码 + 指令"。

**本方向的缝隙（无人同时做）**：
1. **运行时真实观测**的"声明 vs 实际"一致性（BIV 是静态预测 → 我们动态观测）；
2. **蜜罐 per-run 随机标记**把"疑似外传"坐实为"确凿外传"的 ground-truth（现有用 syscall+LLM judge，
   无欺骗取证）；
3. 主攻 SOTA **崩掉**的 PI / agent 控制面偏差（B10–B15）；
4. 从"检测/核验"走到"运行时**阻断**"（deviation → deny）。

---

## 2. 研究问题（RQ）

- **RQ1（一致性刻画）**：在 108 格分类学下，技能 `SKILL.md` **声明的能力/意图** 与 **运行时
  实际观测的行为** 的偏差分布如何？哪些偏差是良性开发者疏忽、哪些是恶意？
- **RQ2（检测增益）**：运行时接地 + 蜜罐取证，能否在 **PI / agent 控制面（B10–B15）** 子集上
  显著优于静态/单轮 LLM/供应链扫描器 baseline？（主指标 F1、Recall；关键看 SOTA 崩掉的类）
- **RQ3（消融）**：静态声明抽取、动态执行观测、蜜罐标记、内核级监控 各组件对
  精度/召回/误报的边际贡献。
- **RQ4（阻断与开销）**：deviation→deny 的阻断成功率、对良性技能（4,000 个）的误阻断率、
  以及运行时延迟/资源开销。

---

## 3. 方法（ShadowBlade v2 核心管线）

```
SKILL.md + 脚本 + 权限声明
   │
   ├─(A) 声明侧：从 SKILL.md/metadata 抽取"声明能力集 + 意图"        [静态 + LLM 抽取]
   │        capability_declared = {fs, net, cred, exec, agent-control, ...}
   │
   ├─(B) 观测侧：带 per-run 随机蜜罐标记的动态沙箱真实执行            [动态观测，不是预测]
   │        - Docker --network none / 限资源 / 即焚（已实现最小闭环）
   │        - 假凭据/假环境注入随机 canary 标记
   │        - CPython audit hook + (计划) seccomp/strace 内核级监控
   │        capability_observed = 实际 open/socket/subprocess/exec/外传 事件
   │        honeypot_hit = canary 标记出现在网络/子进程参数 → 外传 ground-truth
   │
   ├─(C) 一致性比对：typed diff(declared, observed)                   [核验]
   │        deviation = observed \ declared（尤其未声明的外传/控制面写入）
   │
   └─(D) 判定 + 阻断：deviation + honeypot_hit → risk + deny 决策      [阻断]
```

与已发表工作的**一句话差异化**：
> BIV 静态预测 + 只核验；MalSkillBench/USENIX 用 syscall+LLM judge 检测；
> **我们 = 运行时真实观测 + 蜜罐外传取证 + 声明一致性 + 阻断，专打它们崩掉的 PI/控制面。**

现有代码已具备 (B) 的最小闭环（`src/dynamic_engine/`：honeypot/sandbox/monitor/pipeline），
需补 (A) 声明抽取、(C) 一致性比对、(D) 阻断，以及内核级监控与 PI/控制面探针。

---

## 4. 数据集（已本地拉取，可复现）

放在**已 gitignore** 的 `datasets_external/`（不入库、恶意样本只在隔离环境处理）：

- **MalSkillBench**（`github.com/lxyeternal/MalSkillBench`，本地已验证）
  - `Dataset/Skills/malware/`：3,945 个恶意技能，**标签编码在目录名**（如 `__CI_B4`、`__PI_B12`）
  - `Dataset/Skills/benign/`：4,001 个良性技能（误报集）
  - 三维标签：Vector∈{CI,PI,MIXED}；Behavior B1–B15（**B10–B15 = agent 控制面，PI-only**）；
    Insertion 策略；共 108 格
  - `Baselines/`：promptinjection(llama-guard-3/melon/datasentinel/nemo-guardrails/prompt-guard-2/
    attention-tracker)、supplychain(guarddog/malguard/bandit4mal/ossgadget/sap/hercule)、
    skillsecurity(llm-guard/snyk-agent-scan/cisco-skill-scanner/AI-Infra-Guard/多个 skillscan)
- **MaliciousAgentSkillsBench**（USENIX'26，本地已验证）
  - `data/skills_dataset.csv`：98,380（safe 94,093 / suspicious 4,130 / malicious 157）
  - `data/malicious_skills.csv`：157 确认恶意 + Pattern 分类 + Severity
  - 作为**跨数据集泛化**验证 + 野外补充

**数据使用纪律**：只用于防御研究；恶意样本仅在隔离沙箱执行；不重分发；产物脱敏。

---

## 5. Baseline 与评测

- **直接复用 MalSkillBench 自带 baseline** 作对照（省去自建），至少覆盖：
  供应链扫描器（guarddog/bandit4mal）、PI 防御（llama-guard-3/prompt-guard-2）、
  技能安全扫描器（llm-guard 等）、单轮 LLM judge。
- **我方系统**：静态-only / 动态-only / 动态+蜜罐 / 全量（+一致性+阻断）四档消融。
- **指标**：P/R/F1、FPR（在 4,000 良性上）、AUROC/AUPRC；**分 108 格/分 Vector 报告**，
  重点报告 **PI 与 B10–B15** 子集；阻断成功率、误阻断率、延迟、资源开销。
- **划分**：固定随机种子；generated / wild 分开报告（wild 已知偏置：单一加密货币窃取占多数，
  单独报告避免夸大泛化）。
- **可复现**：固定本地开源模型（如 Qwen3-4B，temperature=0）做主实验；闭源模型仅做跨模型鲁棒性
  对比且如实标注不可复现风险。

---

## 6. 威胁模型与局限

- 假设：技能来自不可信第三方；攻击者可能做沙箱探测/延迟激活/混淆。
- 已知局限：Docker 非强隔离边界；Python audit hook 覆盖不到原生/非 Python 载荷（→ 补内核级）；
  动态未触发 ≠ 绝对安全；LLM 抽取存在幻觉（→ 以确定性蜜罐/syscall 证据为主，LLM 为辅）。

---

## 7. 现实时间线（AI 辅助，单人）

| 周 | 目标 |
|---|---|
| W1 | 跑通两个数据集加载 + 复现 2–3 个 baseline（拿到可信对照数） |
| W2 | 实现 (A) 声明抽取 + (C) 一致性比对；把 (B) 动态闭环批量化跑 malware/benign |
| W3 | 补内核级监控 + PI/控制面探针；四档消融跑通；出主表 |
| W4 | (D) 阻断实验 + 开销 + 写初稿 + 挂 arXiv preprint |

> preprint 可用于抢时间戳与考研复试；正式 CCF-C/中文核心 录用通常还需 3–8 个月审稿。

---

## 8. 下一步（P0 具体动作）

1. 写数据加载器：解析 MalSkillBench 目录名标签（Vector/Behavior/Insertion）→ 统一 schema。
2. 选 2 个 baseline（如 guarddog + llama-guard-3）先跑出对照数，确认评测口径。
3. 在 100 个小批（50 mal / 50 benign）上打通 静态声明抽取 + 动态观测 + 一致性比对 端到端。
4. 全部走分支 + PR；恶意样本只在隔离环境。
