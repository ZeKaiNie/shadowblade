# 影刃卫士 - 项目知识库索引

> **AI 助手请先读这个文件**，按需加载子文件。不要一次性读取全部文件。
> 协作规则见根目录 `AGENTS.md`；**换账号/新会话交接看 `docs/HANDOFF.md`**。
> 最后更新：2026-07-18（新增 `docs/HANDOFF.md` 交接书；同步 v2 诱饵扩展 / v3 入口触发实验结论）

## 文件目录

| 文件 | 内容 | 更新频率 |
|------|------|---------|
| `AGENTS.md`（根目录） | AI 协作/编码/学术诚信规则（取代旧 CLAUDE.md/.windsurfrules） | 低 |
| `docs/HANDOFF.md` | **换账号/新会话交接书**：可直接粘的开场白 + 现状/路线/下一步/红线 | 中 |
| `PROJECT_CONTEXT.md`（根目录） | 项目上下文精简版（现状/团队/论文目标） | 中 |
| `docs/progress.md` | 当前进度、待办、里程碑状态 | **高**（每次开发后更新） |
| `docs/planning/` | 客观评估、CCF-C 可行性、v2 架构、**2026 现状调研+方向修正**、**方向A 研究计划** | 高 |
| `docs/architecture.md` | 系统架构、技术栈、威胁模型 | 低 |
| `docs/decisions.md` | 关键技术决策记录 | 低 |
| `docs/research.md` | 竞品/攻击案例/数据集（⚠️ 条目未核实，引用前须查证） | 低 |
| `docs/modules/static_engine.md` | 静态引擎设计细节 | 中 |
| `docs/modules/dynamic_engine.md` | 动态引擎设计细节 | 中 |
| `docs/modules/ai_engine.md` | AI 研判引擎设计细节 | 中 |

## 快速上下文（每次会话必读，新 AI 从这里开始）

- **项目全称**："影刃卫士"(ShadowBlade Guardian)
- **做什么**：面向 AI Agent Skills（SKILL.md / ChatGPT Apps）供应链与运行时安全的**审计与防御研究系统**，
  产出可复现、可发表的方法与实验。
- **核心方法**：**per-run 随机蜜罐/canary 污点取证**——隔离沙箱真实执行 + 运行时行为监控（`sys.addaudithook`）
  抓凭据窃取/外传的"现行"，再与**声明能力**比对做确定性、可解释的 `allow/review/deny`。
- **⭐ 当前研究主线（锁定 A+B，同一套 canary 方法打两个面）**：
  - **方向 A（保底·有公开数据）**：运行时接地能力一致性核验 + 蜜罐取证 + 阻断，基于 **MalSkillBench**，
    专打 SOTA 崩掉的 prompt-injection / agent 控制面（B10–B15）；区别于 BIV 的静态预测。
  - **方向 B（新颖·需自建）**：跨 App 共享上下文投毒的检测/防御/基准（ChatGPT Apps），迁移 canary 污点。**B 不阻塞 A**。
  - **当前进度**：A 的数据/评测/一致性核验/动态沙箱已通，真实 50/50 小批 = 高精度零误报低召回确认层
    （P=1.00/FPR=0.00/Recall=0.16）。诱饵扩展(v2)+入口触发(v3)+可疑目标信誉(v4)已做：均**未提升该批召回**（v4 只把 2 个原 review 样本正确升为 deny、FPR 仍 0）。瓶颈：样本在通用沙箱跑不起来(7 语法错+16 崩溃) + 能力粒度/IOC 覆盖盲区。
    **下一步：样本可执行性（Windows/缺库样本归静态/LLM 路径）+ 扩大 IOC/威胁情报源**。
- **论文目标**：现实定级 **CCF-C / 中文核心 / SCI Q3–Q2**，先挂 arXiv preprint 抢占位（CCF-A/B、SCI Q1 短期不现实）。
- **团队**：3 人，四川轻化工大学网络工程与安全专业，硬件 RTX 4060 8GB，导师可提供云 GPU。
- **仓库**：https://github.com/ZeKaiNie/shadowblade

### 真实现状（详见 `PROJECT_CONTEXT.md` / `docs/progress.md` 顶部）

- ✅ 数据加载器（MalSkillBench 3,944 恶意+4,000 良性）+ 评测框架（P/R/F1/FPR）+ baseline 复现表。
- ✅ 声明能力抽取 + `allowed-tools` 解析 + 声明↔观测一致性核验 + 确定性决策 + 端到端管线。
- ✅ 动态沙箱（Docker `--network none` + 蜜罐 + 审计钩子 + 依赖兜底 shim）；✅ 静态引擎；🟡 AI 研判骨架。
- 🔬 真实 50/50 小批：P=1.00 / FPR=0.00 / Recall=0.16 / F1=0.28 / 蜜罐命中=0（高精度零误报低召回确认层）。
- ✅ 诱饵扩展(v2)、入口触发(v3)、可疑外传目标信誉(v4，独立于“是否声明网络”加权) 已做；机制经合成/单测验证正确，但**同批 50/50 召回均未变**（R=0.16/FPR=0；v4 仅把 Bankr/OSINT 两个原 review 升为 deny）。诊断：50 恶意中 7 语法错/16 运行崩溃/18 有敏感行为、其中 10 如实声明→放行。
- ⬜ 样本可执行性、扩大 IOC/威胁情报源、下载-执行链、方向 B 测试台、消融、跨数据集泛化、论文初稿 未做。
- ❌ 旧文档"15 样本/100% 检出"等指标为编造，已作废，不得引用。

### 代码结构概览

```
src/
├── data_ingestion/    # MalSkillBench 数据加载器（目录名标签解析）✅
│   └── malskillbench_loader.py
├── evaluation/        # 评测框架 ✅
│   ├── metrics.py             # P/R/F1/FPR/混淆矩阵
│   └── malskillbench_baselines.py  # 复现官方 baseline
├── conformance/       # 方向A 方法核心：声明↔观测一致性核验 ✅
│   ├── capabilities.py    # 统一能力分类学 + allowed-tools 解析
│   ├── conformance.py     # 声明↔观测比对 + 决策
│   └── pipeline.py        # 端到端管线
├── dynamic_engine/    # 动态审计引擎（Docker 沙箱/蜜罐/审计钩子）✅
│   ├── honeypot.py / harness.py / sandbox.py / monitor.py / pipeline.py / models.py
│   └── sandbox_shims/     # 缺库依赖兜底 shim（requests/httpx/wget/urllib3/_autostub）
├── static_engine/     # 静态审计引擎 ✅（skill_parser/scanner/pipeline/models）
├── ai_engine/         # AI 研判引擎 🟡（llm_judge/llm_client + ChromaDB+BGE RAG）
├── api/               # FastAPI 后端 ⬜（demo）
└── dashboard/         # Streamlit 前端 ⬜（demo）
scripts/               # run_pilot_batch.py（真实小批实验）/ e2e_smoke_conformance.py
datasets_external/     # 公开数据集（gitignore，不入库）
tests/                 # 单元 + Docker 集成测试（skipif 保护）
config/settings.yaml   # 全局配置
```

### 最近变更
- 07-18 **可疑目标信誉(v4)**：`monitor` 产出 `suspicious_network_targets`、`conformance` 独立于声明加权(0.45)；同 50/50 召回未变(R=0.16/FPR=0)、仅 2 样本 review→deny，已如实记录于 `docs/planning/小批实验结果_方向A.md` 第 5c 节。
- 07-18 **新增交接书 + v2/v3 实验**：加 `docs/HANDOFF.md`（换账号/新会话交接）；诱饵扩展(v2)+入口触发(v3)已实现并诚实记录“未提升本批召回”及原因诊断，见 `docs/planning/小批实验结果_方向A.md` 第 5/5b 节。（PR #6/#8/#9）
- 07-18 **门面/记忆文件同步**：`README.md`、`PROJECT_CONTEXT.md`、本文件快速上下文全部改到**当前 A+B 主线**（旧"ClawHub 审计对象/三引擎"框架下线）；`docs/progress.md` 顶部加"当前主线"横幅、旧 Hermes/MiMo/M里程碑标为历史存档——便于新开对话 AI 快速上手、跟随讨论路线。
- 07-18 **方向A 小批实验**：动态引擎加依赖兜底 shim + allowed-tools 声明解析，真实 MalSkillBench 50恶意/50良性跑通 → Precision=1.00/FPR=0.00/Recall=0.16（高精度零误报低召回），见 `docs/planning/小批实验结果_方向A.md`、`scripts/run_pilot_batch.py`、`src/dynamic_engine/sandbox_shims/`
- 07-18 **P0 数据+评测**：MalSkillBench 数据加载器（3,944恶意+4,000良性）+ 评测框架（P/R/F1/FPR）+ baseline 复现表，见 `src/data_ingestion/malskillbench_loader.py`、`src/evaluation/`、`docs/planning/baseline复现结果_MalSkillBench.md`
- 07-18 **方向决策**：全候选彻底对比后锁定 **A（保底）+ B 跨App上下文投毒（新颖）**，见 `docs/planning/方向决策_全候选彻底对比.md`、`docs/planning/新兴风口调研_下一代Agent安全方向.md`
- 07-18 **联网竞品调研**：核实赛道已饱和（USENIX'26/MalSkillBench/BIV 等预印本），锁定方向 A（运行时接地能力一致性核验+蜜罐取证+阻断），拉取公开数据集，见 `docs/planning/2026现状调研与论文方向修正.md` + `docs/planning/方向A_运行时接地能力一致性核验_研究计划.md`
- 07-18 项目整理：移除个人知识库 `knowledge/`、合并规则为 `AGENTS.md`、精简 `PROJECT_CONTEXT.md`、收录 `docs/planning/`、`research.md` 加未核实警告
- 07-18 动态引擎最小闭环落地并接入综合评分（PR #1 已合入 main）

## 技术栈

- **语言**: Python
- **本地模型**: Qwen3-4B AWQ (vLLM) | **云端**: OpenAI/Anthropic/DeepSeek 等 via LiteLLM（对比实验用）
- **静态扫描**: Semgrep + Bandit + pip-audit + LLM Guard
- **动态沙箱**: Docker（`--network none`）+ CPython 审计钩子（`sys.addaudithook`）+ 蜜罐（内核级监控/libfaketime 规划中）
- **AI 研判**: ChromaDB + BGE-small + RAG
- **后端/前端**: FastAPI / Streamlit（规划中）

## 编码规范

- 类型注解，Pydantic 数据模型。
- **代码必须有中文注释**（覆盖任何全局"不加注释"规则）。
- 优先复用成熟开源工具，不从零造轮子。
- commit message 格式：`[模块] 简要描述`。
- 更多见根目录 `AGENTS.md`。
