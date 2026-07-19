# Baseline 复现结果（MalSkillBench 公开 baseline）

> 来源：MalSkillBench(arXiv:2606.07131) 仓库自带的逐样本预测（`Experiment/Results/`）
> 与官方汇总脚本（`Experiment/RQ3/RQ4/*_baseline_accuracy.py`）。
> **这些数字是 MalSkillBench 作者的 baseline 结果，非本项目原创**，论文引用须标注来源。
> 复现方式：`python -m src.evaluation.malskillbench_baselines`（内部调用官方脚本、解析表格）。
> 正类 = 恶意；全量样本 = 3,944 恶意 + 4,000 良性 = 7,944。

## 全量对照表（P/R/F1/FPR/Acc）

| 类别 | 工具 | Precision | Recall | F1 | FPR | Accuracy |
|---|---|---|---|---|---|---|
| supplychain | bandit4mal | 0.855 | 0.362 | 0.509 | 0.060 | 0.653 |
| supplychain | guarddog | 0.926 | 0.154 | 0.265 | 0.012 | 0.574 |
| supplychain | ossgadget | 0.517 | 0.973 | 0.675 | 0.897 | 0.535 |
| supplychain | malguard--dt | 0.982 | 0.136 | 0.239 | 0.003 | 0.570 |
| supplychain | malguard--rf | 0.996 | 0.071 | 0.133 | 0.000 | 0.539 |
| supplychain | malguard--xgb | 0.995 | 0.101 | 0.183 | 0.001 | 0.553 |
| supplychain | malguard--mlp | 0.993 | 0.151 | 0.262 | 0.001 | 0.578 |
| supplychain | malguard--nb | 1.000 | 0.036 | 0.070 | 0.000 | 0.521 |
| supplychain | malguard--svm | 0.985 | 0.145 | 0.253 | 0.002 | 0.575 |
| supplychain | sap--dt | 0.504 | 0.995 | 0.669 | 0.965 | 0.512 |
| supplychain | sap--rf | 0.867 | 0.003 | 0.007 | 0.001 | 0.505 |
| supplychain | sap--xgb | 0.965 | 0.063 | 0.118 | 0.002 | 0.534 |
| promptinjection | datasentinel | 0.497 | 0.997 | 0.663 | 0.995 | 0.498 |
| promptinjection | llama-guard-3 | 0.988 | 0.129 | 0.228 | 0.002 | 0.567 |
| promptinjection | nemo-guardrails | 0.521 | 0.960 | 0.675 | 0.870 | 0.542 |
| promptinjection | prompt-guard-2 | 0.452 | 0.262 | 0.332 | 0.314 | 0.476 |
| promptinjection | melon | 0.906 | 0.144 | 0.248 | 0.015 | 0.567 |
| promptinjection | attention-tracker | 0.496 | 1.000 | 0.664 | 1.000 | 0.496 |
| skillsecurity | AI-Infra-Guard | 0.846 | 0.866 | 0.856 | 0.155 | 0.856 |
| skillsecurity | cisco-skill-scanner--llm | 0.714 | 0.927 | 0.807 | 0.366 | 0.779 |
| skillsecurity | cisco-skill-scanner--static | 0.785 | 0.356 | 0.490 | 0.096 | 0.632 |
| skillsecurity | llm-guard | 0.591 | 0.446 | 0.509 | 0.304 | 0.572 |
| skillsecurity | NMitchem-skillscan | 0.700 | 0.145 | 0.240 | 0.061 | 0.545 |
| skillsecurity | panguard-skill-auditor--static | 0.762 | 0.186 | 0.299 | 0.057 | 0.567 |
| skillsecurity | skill-security-scan | 0.285 | 0.087 | 0.133 | 0.214 | 0.439 |
| skillsecurity | snyk-agent-scan | 0.932 | 0.287 | 0.438 | 0.021 | 0.635 |
| skillsecurity | getsentry-skill-scanner--full | 0.805 | 0.984 | 0.886 | 0.234 | 0.874 |
| skillsecurity | getsentry-skill-scanner--static | 0.673 | 0.287 | 0.402 | 0.137 | 0.577 |
| skillsecurity | kurtpayne-skillscan-security | 0.566 | 0.840 | 0.676 | 0.635 | 0.601 |
| skillsecurity | virustotal | 0.995 | 0.216 | 0.355 | 0.001 | 0.610 |

## 观察（对方向 A 的意义）

1. **两极分化，几乎没有"高 P 又高 R"的工具**：
   - 供应链/PI 静态或守卫类（guarddog / malguard / llama-guard-3 / snyk）**精确率高但召回极低**
     （recall 常 < 0.3）——漏报严重；
   - 触发型（ossgadget / sap--dt / datasentinel / attention-tracker）**召回接近 1 但 FPR 也接近 1**
     ——基本等于"全判恶意"，无区分力。
2. **表现最好的是"技能安全"类 LLM 扫描器**（getsentry-full F1≈0.886、AI-Infra-Guard F1≈0.856、
   cisco-llm F1≈0.807），但仍有 15%–37% 的误报率。
3. **这正好印证方向 A 的立足点**：现有工具要么漏（低召回），要么吵（高误报），
   我们用"运行时观测 + 蜜罐取证"把"疑似"坐实成"确凿"，目标是**在低 FPR 下提升召回**，
   尤其在 baseline 最弱的 **agent 控制面（B10–B15）** 子集上。

## Agent 控制面子集召回（B10–B15）

> 复现方式：`python -m src.evaluation.subset_baselines`（复用官方 RQ3 各工具 parser，
> 按行为标签过滤 B10–B15 恶意子集，统计召回）。
> 子集全为恶意样本（259 个），无对应良性，故只报**召回率**（= 检出率）。

| 工具 | 全量恶意召回 | 控制面(B10–B15)召回 | 召回下降 |
|---|---|---|---|
| AI-Infra-Guard | 0.866 (3414/3944) | 0.664 (172/259) | -0.202 |
| getsentry-skill-scanner--full | 0.983 (3876/3944) | 0.981 (254/259) | -0.002 |
| cisco-skill-scanner--llm | 0.927 (3657/3944) | 0.761 (197/259) | -0.167 |
| snyk-agent-scan | 0.283 (1116/3944) | 0.151 (39/259) | -0.132 |
| llm-guard | 0.445 (1757/3944) | 0.328 (85/259) | -0.117 |
| virustotal | 0.216 (850/3944) | 0.000 (0/259) | -0.216 |

**诚实解读（不夸大）**：
- 多数检测器在 agent 控制面攻击上召回**明显下降**（AI-Infra-Guard −0.20、cisco-llm −0.17、
  virustotal 从 0.216 直接掉到 **0**）——印证"控制面是薄弱环节"。
- **但并非全部崩塌**：最强的 LLM 扫描器 getsentry-full 在控制面几乎不掉（0.983→0.981）。
  因此论文措辞应为"**多数/传统检测器**在控制面召回显著下降"，而非"所有检测器都崩"。
- 这说明方向 A 的价值不在"替代最强 LLM 扫描器"，而在于用**运行时观测+蜜罐取证**
  提供**确定性、可解释、低误报**的确认层，尤其补齐静态/供应链类工具的控制面盲区。

## 待补（诚实标注）

- 官方 generated/wild/test 划分需作者权威索引，暂缺。
- 控制面子集目前只报召回（子集无良性样本）；如需精确率/FPR，需构造对应良性对照。
