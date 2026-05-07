# 开发进度

> 最后更新：2026-05-07

## 当前状态：M2 静态引擎开发（进行中）

### M1 ✅ 已完成（2026-04-28）
- WSL2 环境 + Python .venv
- Semgrep 1.161.0 + Bandit 1.9.4 + pip-audit 2.10.0
- Docker 29.4.1
- Qwen3-4B-AWQ 模型下载 + vLLM 0.20.0 推理验证通过
- Claude Code + MiMo-V2.5-Pro（原 DeepSeek V4 Pro，已切换）

### M2 进行中
- [x] SKILL.md 解析器（`src/static_engine/skill_parser.py`）— 12 测试通过
- [x] 静态扫描器 Semgrep + Bandit（`src/static_engine/scanner.py`）— 5 测试通过
- [x] AI 研判引擎 LLM 语义分析（`src/ai_engine/llm_judge.py`）— 12 测试通过
- [x] SSD 四子任务 Prompt（`judge_skill_ssd()`）— 参考 SkillSieve 论文
- [x] RAG 知识库 ChromaDB + BGE-small（`src/ai_engine/rag_knowledge.py`）— 8 测试通过
- [x] 恶意样本数据集 10 个 + 正常样本 5 个（`data/malicious/`, `data/benign/`）— 15 集成测试通过
- [x] 云端 API 切换（`src/ai_engine/llm_client.py`）— 支持 vLLM/MiMo/DeepSeek 三者切换，12 测试通过
- [ ] FastAPI 后端框架（`src/api/`）
- [x] 连接 GitHub 远程仓库（`ZeKaiNie/shadowblade` 私有）

### 后续里程碑
- **M3(W6)**: 静态引擎 v1.0 全链路（S1-S6 独立运行）
- **M4(W8)**: 动态引擎 v1.0（Docker+mitmproxy+蜜罐）
- **M5(W10)**: ReAct Agent + pipeline vs agent 对比
- **M6(W12)**: Streamlit 仪表盘 + 批量审计
- **M7(W20)**: 论文初稿
- **M8(W32)**: 结题

## 测试状态：65 测试（60 passed + 5 skipped） ✅

| 测试文件 | 数量 | 状态 |
|---------|------|------|
| `tests/test_skill_parser.py` | 12 | ✅ |
| `tests/test_scanner.py` | 5 | ✅ |
| `tests/test_llm_judge.py` | 12 | ✅（含 vLLM 集成测试 + SSD 子任务测试） |
| `tests/test_llm_client.py` | 13 | ✅（云端 API 配置加载 + 请求构造 + MiMo 集成测试） |
| `tests/test_rag_knowledge.py` | 8 | ✅ |
| `tests/test_real_samples.py` | 15 | ✅（真实样本集成测试） |

## 量化指标目标

- SKILL.md 恶意指令检测率 ≥ 90%
- 静态检出率 ≥ 85%，误报率 ≤ 15%
- 联合检出率 ≥ 92%
- OWASP AST10 覆盖度 ≥ 7/10
- 单技能审计 ≤ 5 分钟
- 系统可在单卡 4060 8GB 稳定运行
