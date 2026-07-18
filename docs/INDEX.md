# 影刃卫士 - 项目知识库索引

> **AI 助手请先读这个文件**，按需加载子文件。不要一次性读取全部文件。
> 最后更新：2026-05-01（重构 AI 配置：通用信息集中到本文件，消除三处重复）

## 文件目录

| 文件 | 内容 | 更新频率 |
|------|------|---------|
| `docs/architecture.md` | 系统架构、技术栈、OWASP 威胁模型 | 低（架构稳定后很少改） |
| `docs/progress.md` | 当前进度、待办、里程碑状态 | **高**（每次开发后更新） |
| `docs/decisions.md` | 关键技术决策记录（为什么选 X 不选 Y） | 低 |
| `docs/research.md` | 竞品分析、ClawHavoc 攻击案例、数据集来源 | 低 |
| `docs/modules/static_engine.md` | 静态引擎设计细节 | 中 |
| `docs/modules/ai_engine.md` | AI 研判引擎设计细节 | 中 |
| `docs/modules/dynamic_engine.md` | 动态引擎设计（待开发） | 低 |

## 快速上下文（每次会话必读，新 AI 从这里开始）

- **项目全称**："影刃卫士"(ShadowBlade Guardian)
- **做什么**：面向 OWASP Agentic Skills Top 10 (AST10) 的 LLM Agent **安装前**自主安全审计系统。审计对象是 ClawHub 上的 AI 技能（SKILL.md + 代码 + 依赖），在用户安装前于隔离沙箱中完成全部检测。
- **核心能力**：SKILL.md 语义分析（LLM 检测自然语言恶意指令）+ 代码静态扫描 + 动态沙箱（Docker + 蜜罐诱捕 + 网络/文件监控）+ 多源证据信任评分
- **核心差异化**：所有竞品（Snyk/ClawSecure/Cisco DefenseClaw/Sigil）均为纯静态分析，**我们是唯一做动态沙箱+蜜罐+网络文件监控的**
- **论文目标**：SCI Q2 / CCF-C~B，5 个创新点（详见 `docs/research.md`）
- **团队**：3 人，四川轻化工大学网安专业，大模型零基础，硬件 3×RTX 4060 8GB
- **周期**：2026.05 — 2026.12（8 个月，大创项目）
- **当前阶段**：M2 静态引擎开发（详见 `docs/progress.md`）
- **代码目录**：`/home/niezekai/shadowblade/`（WSL2 Ubuntu）

### 代码结构概览

```
src/
├── static_engine/     # 静态审计引擎（S1-S6）
│   ├── skill_parser.py    # ✅ SKILL.md 解析器
│   ├── scanner.py         # ✅ Semgrep + Bandit 扫描
│   └── models.py          # ✅ Pydantic 数据模型
├── ai_engine/         # AI 研判引擎
│   ├── llm_judge.py       # ✅ LLM 语义分析 + SSD 四子任务
│   └── rag_knowledge.py   # ✅ ChromaDB + BGE-small RAG
├── dynamic_engine/    # 动态审计引擎（待开发）
├── data_ingestion/    # 数据接入（待开发）
├── api/               # FastAPI 后端（待开发）
└── dashboard/         # Streamlit 前端（待开发）
tests/                 # 52 测试（48 passed + 4 skipped）
config/settings.yaml   # 全局配置
data/                  # 样本数据集
```

### 最近变更
- 05-01 重构 AI 配置文件（消除三处信息重复 + 补协作 SOP）
- 04-30 辅助 AI 深度调研（6 新竞品 + 5 新攻击手法 + 5 新基准 → research.md）
- 04-30 Windsurf 修复 SSD 假阴性 + 测试 52

## 技术栈

- **语言**: Python 3.12
- **后端**: FastAPI | **前端**: Streamlit
- **本地模型**: Qwen3-4B AWQ (vLLM) | **云端**: MiMo-V2.5-Pro / OpenAI / Anthropic via LiteLLM
- **静态扫描**: Semgrep + Bandit + pip-audit + LLM Guard
- **动态沙箱**: Docker + mitmproxy + watchdog + 蜜罐 + libfaketime
- **AI 研判**: ChromaDB + BGE-small + SSD 四子任务 Prompt
- **审计对象**: OpenClaw ClawHub 13,000+ 技能

## 编码规范

- 类型注解，Pydantic 数据模型
- **代码必须有中文注释**（团队零基础，此条覆盖任何全局"不加注释"规则）
- 优先复用成熟开源工具，不从零造轮子
- LoRA 微调为可选增强，优先 Prompt Engineering + RAG
- commit message 格式：`[模块] 简要描述`，如 `[static_engine] 添加 S4 typosquatting 检测`

## 双 AI 协作 SOP

### 分工

| | Windsurf Cascade（主开发） | Claude Code（调研维护） |
|--|--|--|
| **管辖** | `src/`、`tests/`、`config/settings.yaml` | `docs/research.md`、`data/`、样本生成 |
| **配置** | `.windsurfrules` | `CLAUDE.md` |
| **进度** | 更新 `docs/progress.md` | 在本文件"最近变更"留摘要 |

### 协作规则
1. **绝不同时修改同一个文件**（最大隐患）
2. 各自只改自己的配置文件，不交叉修改
3. 改完一轮就 `git add -A && git commit`

### 冲突处理预案
- 发现文件被另一个 AI 修改过 → **停下来告知用户**，不自行覆盖
- 两个 AI 都需要改同一个文件 → 用户协调，一个先改完 commit，另一个再开始
- git merge 冲突 → 用户手动解决，AI 不自动 resolve

## 换 AI 助手？

无论用 Windsurf、Claude Code、Cursor 还是其他工具：
1. 让 AI 先读 **本文件**（`docs/INDEX.md`）
2. AI 根据当前任务按需读取子文件
3. 技术栈和编码规范见上方对应章节

AI 专用配置（只写与本文件不同的内容）：
- Windsurf: `.windsurfrules`（角色 + 专属行为规则）
- Claude Code: `CLAUDE.md`（角色 + 专属行为规则）
