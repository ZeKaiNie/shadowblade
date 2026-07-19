# 🛡️ 影刃卫士 ShadowBlade Guardian

> **AI 助手请先读 `docs/INDEX.md`**（知识库入口）与根目录 `AGENTS.md`（协作/学术诚信规则），按需加载子文件。
> 当前研究主线、真实进度见下文「研究主线」与 `docs/progress.md` 顶部。

面向 **AI Agent Skills（Anthropic Skills / SKILL.md、ChatGPT Apps）** 供应链与运行时安全的**审计与防御研究系统**。目标是产出可复现、可发表（现实定级 **CCF-C / 中文核心 / SCI Q3–Q2**，先挂 arXiv preprint 抢占位）的方法与实验。

## 研究主线（当前锁定：A + B）

赛道到 2026 年已较拥挤（USENIX Sec'26《Do Not Mention…》、MalSkillBench、BIV 等多为预印本）。我们选一个"窄而实、别人没合起来做"的缝隙，用**同一套 per-run 随机蜜罐/canary 污点取证方法**打两个面：

- **方向 A（保底 · 有公开数据）——运行时接地的能力一致性核验 + 蜜罐取证 + 阻断**
  从 `SKILL.md`/`allowed-tools`/元数据抽取**声明能力**，在隔离沙箱真实执行观测**实际能力**，比对差异；每次执行注入随机蜜罐标记（假凭据/身份文件），命中即为"抓现行"的确凿外传证据 → 确定性、可解释的 `allow/review/deny`。差异化：BIV 是**静态预测**能力且只核验，我们**运行时真实观测 + 蜜罐取证 + 阻断**，专打 SOTA 崩掉的 prompt-injection / agent 控制面（MalSkillBench B10–B15）。
- **方向 B（新颖 · 需自建测试台）——跨 App 共享上下文投毒的检测/防御/基准**
  ChatGPT Apps 多 App 共享同一段扁平上下文，恶意 App 可投毒影响后续良性 App（Confused ChatGPT 只做了攻击，检测/防御/基准空白）。我们搭**开源替身测试台**，把 canary 污点思路迁移做跨 App 污点追踪与防御基准。**B 不阻塞 A**：A 先锁保底，B 拉高上限。

> 详细竞品调研、缝隙分析与研究计划见 `docs/planning/`（`2026现状调研与论文方向修正.md`、`方向A_运行时接地能力一致性核验_研究计划.md`、`方向决策_全候选彻底对比.md`）。

## 数据集（真实公开，不再自造）

- **MalSkillBench**（arXiv 2606.07131）：本地统计 **恶意 3,944 + 良性 4,000 = 7,944**，文件夹名编码三维标签（向量 CI/PI/MIXED × 行为 B1–B15 × 插入策略），**B10–B15 = agent 控制面攻击**（主攻靶子），并自带十余个 baseline（guarddog / llama-guard-3 / llm-guard / snyk-agent-scan 等）。
- **MaliciousAgentSkillsBench**（USENIX Sec'26）：98,380 快照 + 157 确认恶意，作跨数据集泛化验证。
- 数据放在已 gitignore 的 `datasets_external/`，**恶意样本只在隔离沙箱执行，不入库、不重分发、不上传闭源云**。

## 开发状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 数据加载器（MalSkillBench） | ✅ | 解析目录名标签 → 统一 `MalSkillSample`；实测 3,944 恶意 + 4,000 良性 |
| 评测框架 + baseline 复现 | ✅ | P/R/F1/FPR/混淆矩阵；复现官方 baseline 对照表 |
| 声明能力抽取 + 一致性核验 | ✅ | 统一能力分类学（含 `identity_write`=控制面）+ `allowed-tools` 解析 + 确定性决策 |
| 动态沙箱 + 蜜罐 + 依赖兜底 shim | ✅ | Docker `--network none`/限资源 + `sys.addaudithook` 行为探针 + 随机蜜罐 + 缺库 shim |
| 静态引擎 | ✅ | SKILL.md 解析 + Semgrep/Bandit/pip-audit + LLM 语义研判（作对照/融合） |
| AI 研判（RAG） | 🟡 | ChromaDB + BGE-small 骨架 |
| **诱饵扩展**（假钱包/助记词/`~/.aws`/浏览器路径） | ⬜ 下一步 | 对上加密货币窃取主流靶子，提蜜罐命中率与召回 |
| 可疑目标信誉 + 下载-执行链规则 | ⬜ | 进一步提召回 |
| 方向 B 开源测试台 + 防御基准 | ⬜ | 跨 App 共享上下文投毒 |
| 消融 + 跨数据集泛化 + 论文初稿 | ⬜ | 只用真实跑出的数据 |

## 第一手实验结果（真实 · 未编造）

真实 MalSkillBench **50 恶意 + 50 良性**（含 Python 脚本可执行子集），隔离 Docker 执行、固定随机种子：

| 指标 | 值 |
|------|----|
| Precision | **1.00** |
| FPR | **0.00**（良性 50 个 0 误报） |
| Recall | **0.16** |
| F1 | 0.28 |
| 蜜罐命中 | 0 |
| 混淆矩阵 | TP=8, FP=0, FN=42, TN=50 |

**诚实定位**：方向 A 目前是**高精度、零误报、低召回的确认层**（不取代最强扫描器，而是提供确定性、可解释、几乎不误报的运行时确认）。召回低的真实原因与下一步（诱饵扩展等）见 `docs/planning/小批实验结果_方向A.md`。

> ❌ 旧文档中"15 样本 / 100% 检出 / 0% 误报"等为编造指标，**已作废，不得引用**。

## 技术栈

- **语言**：Python（类型注解 + Pydantic），代码带中文注释。
- **数据/评测**：MalSkillBench + MaliciousAgentSkillsBench；自研 `src/evaluation`（P/R/F1/FPR）。
- **动态沙箱**：Docker（`--network none` + 限内存/CPU/PID + 即焚 workspace）+ CPython 审计钩子（`sys.addaudithook`）+ per-run 随机蜜罐 + 依赖兜底 shim。
- **静态**：Semgrep + Bandit + pip-audit + LLM Guard。
- **模型**：本地 Qwen3-4B AWQ（vLLM）；云端多模型经 LiteLLM 切换（对比实验用；恶意样本默认不上传闭源云）。

## 项目结构

```
src/
├── data_ingestion/    # MalSkillBench 数据加载器（目录名标签解析）✅
├── evaluation/        # 评测框架（P/R/F1/FPR）+ baseline 复现 ✅
├── conformance/       # 声明能力抽取 + 声明↔观测一致性核验 + 决策 ✅
├── dynamic_engine/    # Docker 沙箱 + 蜜罐 + 审计钩子 + 依赖兜底 shim ✅
├── static_engine/     # 静态审计（Semgrep/Bandit/pip-audit/LLM 语义）✅
├── ai_engine/         # RAG 研判（ChromaDB + BGE-small）🟡
├── api/ dashboard/    # FastAPI / Streamlit（demo，非论文关键路径）⬜
scripts/               # run_pilot_batch.py（真实小批实验）等
datasets_external/     # 公开数据集（gitignore，不入库）
docs/                  # INDEX.md 知识库入口 + planning/ 研究计划 + progress.md
tests/                 # 单元 + Docker 集成测试（skipif 保护）
```

## 运行测试

```bash
source .venv/bin/activate
python -m pytest -q                       # 全套（需 chromadb 才跑 RAG 用例）
python -m pytest tests/test_conformance.py tests/test_sandbox_shims.py -v
```

## 安全提示

动态引擎处理陌生/恶意代码**必须**在 Docker 隔离沙箱内执行（`--network none` + 限资源 + 即焚）；无 Docker 时不会自动在宿主机运行，除非显式 `allow_unsafe_subprocess=True`（仅供本地测试合成代码，**切勿用于真实恶意样本**）。

## 团队 / 硬件

四川轻化工大学 大创项目团队（3 人）；硬件 RTX 4060 Laptop 8GB，导师可提供云 GPU。

## 许可证

MIT License
