# 影刃卫士 - 项目知识库索引

> **AI 助手请先读这个文件**，按需加载子文件。不要一次性读取全部文件。
> 最后更新：2026-04-29（竞品审查刷新 + SSD 四子任务 Prompt + DDIPE 威胁覆盖）

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

## 快速上下文（每次会话必读）

- **项目一句话**："影刃卫士"——面向 OWASP AST10 的 LLM Agent 自主安全审计系统，融合 SKILL.md 语义分析 + 动态蜜罐诱捕 + 多源证据信任评分
- **团队**：3 人，网安专业，大模型零基础，硬件 3×RTX 4060 8GB
- **周期**：2026.05 — 2026.12（8 个月）
- **当前阶段**：M2 静态引擎开发（详见 `docs/progress.md`）
- **代码目录**：`/home/niezekai/shadowblade/`（WSL2 Ubuntu）
- **编码规范**：Python 3.12，类型注解，Pydantic，中文注释，复用开源工具

## 换 AI 助手？

无论用 Windsurf、Claude Code、Cursor 还是其他工具：
1. 让 AI 先读 **本文件**（`docs/INDEX.md`）
2. AI 根据当前任务按需读取子文件
3. 编码规范和技术栈见上方"快速上下文"

AI 专用配置（非通用）：
- Windsurf: `.windsurfrules`
- Claude Code: `CLAUDE.md`
