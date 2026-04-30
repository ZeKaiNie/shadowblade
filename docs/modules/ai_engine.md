# AI 研判引擎

## 文件清单

| 文件 | 作用 | 测试 |
|------|------|------|
| `src/ai_engine/llm_judge.py` | LLM 语义分析（Prompt Engineering） | 9 tests |
| `src/ai_engine/rag_knowledge.py` | RAG 知识库（ChromaDB + BGE-small） | 8 tests |

## LLM 研判（llm_judge.py）

- **judge_skill()**: 综合研判入口，分析功能一致性、权限合理性、提示注入等
- **judge_prerequisites()**: 专项分析 prerequisites 段落（ClawHavoc 主攻入口）
- 调用 vLLM OpenAI 兼容 API（`http://127.0.0.1:8000/v1`）
- 参数 `api_base` 和 `model` 可切换，支持本地/云端
- 支持 RAG：传入 `rag_knowledge_base` 参数自动检索相关情报

## RAG 知识库（rag_knowledge.py）

- **ChromaDB** 持久化向量存储（`data/chromadb/`）
- **BGE-small-zh-v1.5** 嵌入模型（CPU 运行，512 维向量）
- 默认灌入 12 条安全知识：
  - ClawHavoc 攻击模式 4 条
  - ToxicSkills 攻击模式 3 条
  - OWASP AST10 安全规则 4 条
  - 威胁情报 IOC 1 条
- `init_knowledge_base()` 幂等初始化（不重复灌入）

## Prompt 模板

三个模板均要求 LLM 返回结构化 JSON：
- `SKILL_AUDIT_PROMPT`: 综合审计（含 RAG 参考情报段）—— 单一宽泛Prompt，作为 baseline
- `PREREQ_AUDIT_PROMPT`: prerequisites 专项审计

### SSD 四子任务（v2 新增，参考 SkillSieve）

- `SSD_INTENT_PROMPT`: 意图一致性检查（权重0.35）— 声称功能 vs 实际行为
- `SSD_PERMISSION_PROMPT`: 权限合理性检查（权重0.25）— 声明权限 vs 功能需求
- `SSD_COVERT_PROMPT`: 隐蔽行为检测（权重0.25）— 隐藏/伪装/延迟激活
- `SSD_CROSSFILE_PROMPT`: 跨文件一致性检查（权重0.15）— SKILL.md vs 代码脚本
- `SSD_FUSION_PROMPT`: 四子任务融合判定（加权综合）

`judge_skill_ssd()` 函数实现四子任务独立分析 + 融合判定。
论文实验可对比 `judge_skill()` (单Prompt) vs `judge_skill_ssd()` (SSD) 的 F1 差异。
