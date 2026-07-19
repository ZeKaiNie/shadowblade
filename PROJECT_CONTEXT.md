# 影刃卫士 - 项目上下文（精简版）

> ⚠️ 本文件已于 2026-07-18 精简重写。旧的 460 行详细规划（含大量未核实数据、过时的
> 双 AI 分工、WSL 本地路径、"SCI Q2/CCF-B"等激进目标）已废弃。
> **知识库入口是 `docs/INDEX.md`**；整体重构与论文规划见 `docs/planning/`。

## 一句话

**影刃卫士（ShadowBlade Guardian）**——面向 AI Agent Skills（SKILL.md / ChatGPT Apps）供应链与运行时
安全的**审计与防御研究系统**。核心方法是 **per-run 随机蜜罐/canary 污点取证**：把技能放进隔离沙箱真实
执行，用运行时行为监控（`sys.addaudithook`）捕获它对假凭据/身份文件的窃取与外传，命中即"抓现行"的确凿
证据，再与**声明能力**比对做确定性、可解释的 `allow/review/deny`。

## 当前研究主线（锁定 A + B，用同一套 canary 方法打两个面）

- **方向 A（保底 · 有公开数据）**：运行时接地的能力一致性核验 + 蜜罐取证 + 阻断。基于公开
  **MalSkillBench**，专打 SOTA 崩掉的 prompt-injection / agent 控制面（B10–B15）。
  差异化：BIV 静态预测且只核验，我们**运行时真实观测 + 蜜罐取证 + 阻断**。
- **方向 B（新颖 · 需自建）**：跨 App 共享上下文投毒的检测/防御/基准（ChatGPT Apps 共享扁平上下文）。
  搭开源替身测试台，迁移 canary 污点做跨 App 追踪。**B 不阻塞 A**。
- 目标定级：**CCF-C / 中文核心 / SCI Q3–Q2**，先挂 arXiv preprint 抢占位；CCF-A/B、SCI Q1 短期不现实。
- 详见 `docs/planning/`（现状调研+方向修正、方向A 研究计划、全候选对比）。

## 真实现状（2026-07）

- ✅ **数据加载器**（MalSkillBench，实测恶意 3,944 + 良性 4,000）+ **评测框架**（P/R/F1/FPR）+ baseline 复现表。
- ✅ **一致性核验**：统一能力分类学（含 `identity_write`=控制面）+ `allowed-tools` 解析 + 确定性决策 + 端到端管线。
- ✅ **动态引擎**：Docker `--network none` 沙箱 + 蜜罐随机标记 + `sys.addaudithook` 行为探针 + **依赖兜底 shim**。
- ✅ **静态引擎**：SKILL.md 解析 + Semgrep/Bandit/pip-audit + LLM 语义研判（作对照/融合）。
- 🟡 **AI 研判**：RAG（ChromaDB + BGE-small）骨架。
- 🔬 **第一手真实结果**（50 恶意/50 良性含脚本子集）：Precision=1.00、FPR=0.00、Recall=0.16、F1=0.28、蜜罐命中=0
  —— **高精度、零误报、低召回的确认层**（诚实定位，见 `docs/planning/小批实验结果_方向A.md`）。
- ⬜ **未做**：诱饵扩展、可疑目标信誉、下载-执行链规则、方向 B 测试台、消融、跨数据集泛化、论文初稿。
- ❌ **已作废**：此前"15 样本 / 100% 检出 / 0% 误报"等指标为编造，不得引用。

## 团队 / 硬件 / 环境

- 3 人，四川轻化工大学网络工程与安全专业，大模型基础薄。
- 硬件：笔记本 + RTX 4060 Laptop 8GB；导师可提供云 GPU。
- 开发环境：WSL2 + Ubuntu；本地模型 Qwen3-4B AWQ（vLLM），云端模型经 LiteLLM 可切换（对比实验用）。
- 代码仓库：https://github.com/ZeKaiNie/shadowblade

## 论文目标（现实定级）

- 现实可及：**CCF-C 会议 / 中文核心 / SCI Q3–Q2**。
- 短期不现实：CCF-A/B 顶会、SCI Q1。
- 关键：能否发表取决于**数据集 + baseline 对照 + 消融 + 抗规避评估**这套实证严谨度，
  而非功能数量。详见 `docs/planning/影刃卫士_CCFC论文可行性与排期优化.md`。

## 核心差异化（论文卖点）

1. **per-run 随机蜜罐/canary 标记 → 运行时外传取证**（确定性、可复现、不依赖 LLM）——headline，跨 A/B 两面复用。
2. **声明能力 vs 运行时实际观测**的一致性核验（区别于 BIV 的静态预测），专打 prompt-injection / agent 控制面（B10–B15）。
3. **方向 B 首个跨 App 共享上下文投毒的检测/防御基准**（Confused ChatGPT 只做攻击，防御侧空白）。
4. Agent 身份/记忆持久化后门检测（`identity_write` 能力，如 SOUL.md/MEMORY.md/AGENTS.md）。
5. （次要）静态 + 多模型 LLM 语义研判作对照与融合，不作主创新。
6. （可选高风险）分层行为监控内核级(eBPF/seccomp)、抗规避(libfaketime) 作为上限扩展，非当前主线。

## 下一步优先级（当前主线 A+B）

1. **诱饵扩展**（最高性价比提召回、保持零误报）：假加密钱包/助记词、`~/.aws/credentials`、浏览器数据路径等，
   对上 MalSkillBench 主流的加密货币窃取靶子，提升蜜罐命中率。
2. 可疑网络目标信誉信号（Discord CDN / paste / 硬编码 IP / C2）+ 下载-执行链组合规则。
3. 重跑 50/50（乃至更大批）小批，产出提升后的 P/R/F1；PI/MD-only 样本走静态+LLM 路径。
4. 消融（static-only / dynamic-only / +honeypot / full policy）+ MaliciousAgentSkillsBench 跨数据集泛化。
5. 方向 B 开源测试台 + 防御基准（不阻塞 A）。
6. 论文实验表 + 初稿 + arXiv preprint（只用真实跑出的数据）。

> 完整研究计划见 `docs/planning/方向A_运行时接地能力一致性核验_研究计划.md` 与 `docs/planning/方向决策_全候选彻底对比.md`。
