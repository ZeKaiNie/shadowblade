# 🛡️ 影刃卫士 ShadowBlade Guardian

基于 Qwen3-4B 的 AI Agent 供应链安全审计系统，以 OpenClaw/ClawHub 13,000+ 真实技能为审计对象。

## 项目简介

AI Agent 技能市场（如 ClawHub）正在快速增长，但缺乏系统化的安全审计手段。影刃卫士通过**静态分析 + 动态沙箱 + AI 研判**三引擎协同，自动检测技能中的恶意代码、数据窃密、提示词注入等安全威胁。

## 技术栈

- **模型**: Qwen3-4B AWQ 4-bit 量化 (vLLM 推理)
- **静态审计**: Semgrep + Bandit + pip-audit + LLM Guard
- **动态审计**: Docker 沙箱 + mitmproxy + watchdog + 蜜罐
- **AI 研判**: ChromaDB + BGE-small + Qwen3-4B RAG
- **后端**: FastAPI | **前端**: Streamlit

## 项目结构

```
src/
├── static_engine/    # 静态审计引擎（Semgrep/Bandit/pip-audit/LLM Guard/LLM语义审查）
├── dynamic_engine/   # 动态审计引擎（Docker沙箱/mitmproxy/watchdog/蜜罐）
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

## 硬件要求

- NVIDIA GPU ≥ 8GB 显存（RTX 4060 Laptop 可运行）
- WSL2 + Ubuntu 22.04（推荐）

## 团队

四川轻化工大学 大创项目团队

## 许可证

MIT License
