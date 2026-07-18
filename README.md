# 🛡️ 影刃卫士 ShadowBlade Guardian

> **AI 助手请先读 `docs/INDEX.md`**，那是项目知识库入口，按需加载子文件。

基于 Qwen3-4B 的 AI Agent 供应链安全审计系统，以 OpenClaw/ClawHub 13,000+ 真实技能为审计对象。

## 项目简介

AI Agent 技能市场（如 ClawHub）正在快速增长，但缺乏系统化的安全审计手段。影刃卫士通过**静态分析 + 动态沙箱 + AI 研判**三引擎协同，自动检测技能中的恶意代码、数据窃密、提示词注入等安全威胁。

核心思路：不止"猜"技能是不是恶意，而是把它放进**布满蜜罐诱饵的隔离沙箱**里真实执行，用 CPython 审计钩子捕获运行时行为——一旦它去偷假凭据并往外发，蜜罐随机标记会在网络/子进程参数里现形，形成"抓现行"的确凿证据。

## 开发状态

| 引擎 / 模块 | 状态 | 说明 |
|------|------|------|
| 静态审计引擎 | ✅ 已完成 | SKILL.md 解析 + Semgrep/Bandit/pip-audit + 隐写检测 + LLM 语义研判 + 风险评分 |
| 动态审计引擎 | 🟡 最小闭环已落地 | Docker 沙箱（断网/限资源/即焚）+ 蜜罐诱饵 + 审计钩子行为监控 + 研判打分，已接入综合评分 |
| ├ 内核级监控 (eBPF/seccomp) | ⬜ 待开发 | 补 Python 审计钩子的盲区（非 Python/原生载荷、抗规避） |
| ├ libfaketime 时间伪造 | ⬜ 待开发 | 用于触发延迟激活的恶意代码 |
| ├ 多次执行行为对比 | ⬜ 待开发 | 正常 vs 伪造 48h 后行为差异 |
| 数据集 + 评测框架 | ⬜ 待开发（论文生命线） | 攻击分类学 + 数百级标注样本 + P/R/F1/FPR + baseline/消融 |
| AI 研判引擎 | 🟡 部分 | RAG 检索/信任评分已有骨架 |
| 数据接入 / FastAPI / Streamlit | ⬜ 待开发 | demo 级，非论文关键路径 |

> 详细进度见 `docs/progress.md`；动态引擎设计见 `docs/modules/dynamic_engine.md`；整体重构与论文规划见 `docs/planning/`。

## 技术栈

- **模型**: Qwen3-4B AWQ 4-bit 量化 (vLLM 推理)
- **静态审计**: Semgrep + Bandit + pip-audit + LLM Guard
- **动态审计**: Docker 沙箱 + CPython 审计钩子（`sys.addaudithook`）+ 蜜罐（内核级监控 / libfaketime 规划中）
- **AI 研判**: ChromaDB + BGE-small + Qwen3-4B RAG
- **后端**: FastAPI | **前端**: Streamlit

## 项目结构

```
src/
├── static_engine/    # 静态审计引擎（Semgrep/Bandit/pip-audit/LLM Guard/LLM语义审查）
├── dynamic_engine/   # 动态审计引擎（Docker沙箱/蜜罐/审计钩子行为监控）
├── ai_engine/        # AI研判引擎（RAG检索/信任评分/报告生成）
├── data_ingestion/   # 数据接入（ClawHub爬虫/SKILL.md解析）
├── api/              # FastAPI 后端API
└── dashboard/        # Streamlit 可视化仪表盘
config/               # 配置文件 + Semgrep自定义规则
models/               # Qwen3-4B 量化模型
data/                 # 数据集（恶意/良性样本 + RAG知识库）
sandbox/              # Docker沙箱相关文件
tests/                # 测试
```

## 快速开始

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 vLLM 模型服务（需要GPU）
# python -m vllm.entrypoints.openai.api_server --model models/qwen3-4b-awq ...

# 4. 启动后端
# uvicorn src.api.main:app --host 0.0.0.0 --port 8888

# 5. 启动仪表盘
# streamlit run src/dashboard/app.py
```

### 运行测试

```bash
# 全套测试（需要 chromadb 才能跑 RAG 相关用例）
python -m pytest -q
# 动态引擎测试（Docker 集成用例在无 Docker 时自动跳过）
python -m pytest tests/test_dynamic_engine.py -v
```

### 用法示例

```python
from src.static_engine.pipeline import audit_skill

# 静态 + 动态沙箱协同审计（默认关闭动态，显式开启）
result = audit_skill(skill_md_content, enable_dynamic=True)  # 默认走 Docker，无 Docker 时优雅降级
print(result.risk_level, result.risk_score)
print(result.dynamic_findings)   # 动态发现（蜜罐命中/身份文件篡改/外联等）

# 或单独调用动态引擎
from src.dynamic_engine.pipeline import audit_dynamic
dyn = audit_dynamic(code_blocks, code_languages, backend="docker")
print(dyn.risk_score, dyn.honeypot_triggered, dyn.finding_texts)
```

> ⚠️ 安全提示：动态引擎默认必须在 Docker 隔离沙箱中执行陌生代码；无 Docker 时不会自动在宿主机运行，除非显式 `allow_unsafe_subprocess=True`（仅供本地测试，切勿用于真实恶意样本）。

## 硬件要求

- NVIDIA GPU ≥ 8GB 显存（RTX 4060 Laptop 可运行）
- WSL2 + Ubuntu 22.04（推荐）

## 团队

四川轻化工大学 大创项目团队

## 许可证

MIT License
