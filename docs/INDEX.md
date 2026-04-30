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

## 重要：2026-04-29 辅助AI变更摘要（主AI请读）

> 以下变更是辅助AI（Claude Code）在 2026-04-29 完成的。主AI（Windsurf Cascade）请审核并决定是否采纳。

### 变更背景
赛道在 2026年3-4月集中爆发——Permiso SandyClaw（动态沙箱）、SkillSieve（学术三层框架，已开源）、微步 SafeSkill（商业4引擎）、SkillProbe（多Agent审计）、DDIPE（新型攻击）。项目原"唯一动态检测"差异化已失效。

### 已修改的文件
| 文件 | 改动 | 原因 |
|------|------|------|
| `docs/research.md` | 竞品表5→8，新增 SandyClaw/SkillSieve/SafeSkill/SkillProbe；新增 DDIPE 攻击专节 | 原竞品表已过时 |
| `docs/architecture.md` | 差异化从"唯一动态"改为"四合一闭环"；新增扩展威胁覆盖表（DDIPE等） | SandyClaw 也做动态沙箱 |
| `docs/decisions.md` | 新增2条决策：SSD四子任务、四合一差异化定位 | 记录技术选型依据 |
| `docs/modules/ai_engine.md` | 新增 SSD 四子任务章节 | 模块文档同步 |
| `src/ai_engine/llm_judge.py` | 新增6个Prompt模板+`judge_skill_ssd()`函数 | 参考 SkillSieve，F1 预期提升 |

### 需要注意的开源成果
- **[SkillSieve](https://arxiv.org/abs/2604.06550)**：已开源代码+数据+400样本基准，F1=0.800。**强烈建议 clone 研究**，可将其作为 baseline，论证加入动态沙箱+蜜罐后的提升
- **[DDIPE 论文](https://arxiv.org/abs/2604.03081)**：新型攻击向量，11.6%-33.5%绕过率。我们的 S1 语义分析理论上可覆盖，但需针对性验证
- **[SkillProbe](https://arxiv.org/abs/2603.21019)**：多Agent审计+组合风险模拟，skillhub.holosai.io 可体验

### 建议主AI下一步
1. 审核所有变更，决定是否采纳
2. 研究 SkillSieve 开源代码（GitHub），评估可复用部分（XGBoost筛、三模型陪审团）
3. 用 SkillSieve 的 400 样本基准扩充我们的测试集
4. 决定是否在 M2 阶段就引入 SSD（而非等到 M5），加速核心创新
