# 影刃卫士 - 项目知识库索引

> **AI 助手请先读这个文件**，按需加载子文件。不要一次性读取全部文件。
> 协作规则见根目录 `AGENTS.md`。
> 最后更新：2026-07-18（清理旧双 AI 分工 + 收录 planning + 校正现状与论文目标）

## 文件目录

| 文件 | 内容 | 更新频率 |
|------|------|---------|
| `AGENTS.md`（根目录） | AI 协作/编码/学术诚信规则（取代旧 CLAUDE.md/.windsurfrules） | 低 |
| `PROJECT_CONTEXT.md`（根目录） | 项目上下文精简版（现状/团队/论文目标） | 中 |
| `docs/progress.md` | 当前进度、待办、里程碑状态 | **高**（每次开发后更新） |
| `docs/planning/` | 客观评估、CCF-C 论文可行性、v2 架构重构设计 | 中 |
| `docs/architecture.md` | 系统架构、技术栈、威胁模型 | 低 |
| `docs/decisions.md` | 关键技术决策记录 | 低 |
| `docs/research.md` | 竞品/攻击案例/数据集（⚠️ 条目未核实，引用前须查证） | 低 |
| `docs/modules/static_engine.md` | 静态引擎设计细节 | 中 |
| `docs/modules/dynamic_engine.md` | 动态引擎设计细节 | 中 |
| `docs/modules/ai_engine.md` | AI 研判引擎设计细节 | 中 |

## 快速上下文（每次会话必读，新 AI 从这里开始）

- **项目全称**："影刃卫士"(ShadowBlade Guardian)
- **做什么**：面向 AI Agent 技能供应链的安全审计系统。审计对象是技能包（SKILL.md + 代码 + 依赖），
  在隔离沙箱中真实执行并监控运行时行为。
- **核心思路**：蜜罐诱饵 + 隔离沙箱真实执行 + 运行时行为取证（"抓现行"），辅以静态扫描 + LLM 语义研判。
- **核心差异化**：per-run 随机蜜罐标记外传取证 + 分层行为监控（Python 钩子 + 内核级）+ Agent 身份文件后门检测。
- **论文目标**：现实定级 **CCF-C / 中文核心 / SCI Q3–Q2**（CCF-A/B、SCI Q1 短期不现实）。
- **团队**：3 人，四川轻化工大学网络工程与安全专业，硬件 RTX 4060 8GB。
- **仓库**：https://github.com/ZeKaiNie/shadowblade

### 真实现状（详见 `PROJECT_CONTEXT.md` / `docs/progress.md`）

- ✅ 静态引擎；🟡 动态引擎最小闭环已落地并接入综合评分；🟡 AI 研判有骨架。
- ⬜ 数据集+评测框架、内核级监控、libfaketime、多次执行、数据接入、FastAPI、Streamlit 未做。
- ❌ 旧文档"15 样本/100% 检出"等指标为编造，已作废，不得引用。

### 代码结构概览

```
src/
├── static_engine/     # 静态审计引擎 ✅
│   ├── skill_parser.py    # SKILL.md 解析器
│   ├── scanner.py         # Semgrep + Bandit 扫描
│   ├── pipeline.py        # audit_skill 主流水线
│   └── models.py          # 数据模型
├── ai_engine/         # AI 研判引擎 🟡（骨架）
│   ├── llm_judge.py / llm_client.py
│   └── rag_knowledge.py   # ChromaDB + BGE-small RAG
├── dynamic_engine/    # 动态审计引擎 🟡（最小闭环）
│   ├── honeypot.py / harness.py / sandbox.py / monitor.py / pipeline.py / models.py
├── data_ingestion/    # 数据接入 ⬜
├── api/               # FastAPI 后端 ⬜
└── dashboard/         # Streamlit 前端 ⬜
tests/                 # 单元 + Docker 集成测试（skipif 保护）
config/settings.yaml   # 全局配置
```

### 最近变更
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
