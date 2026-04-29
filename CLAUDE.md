# 影刃卫士 ShadowBlade Guardian

## 项目简介
AI Agent技能(Skills)供应链安全审计系统。在用户安装/运行技能之前，在隔离沙箱中完成全部审计。

## 技术栈
- Python 3.12, FastAPI, Streamlit
- Qwen3-4B AWQ 4-bit量化 (vLLM推理)
- 静态: Semgrep + Bandit + pip-audit
- 动态: Docker沙箱 + mitmproxy + watchdog + 蜜罐
- AI研判: ChromaDB + BGE-small + Qwen3-4B RAG
- 模型可插拔: LiteLLM统一接口

## 项目结构
- `config/settings.yaml` - 主配置文件
- `PROJECT_CONTEXT.md` - 完整项目上下文（详细版）
- `requirements.txt` - Python依赖

## 编码规范
- 类型注解，Pydantic数据模型
- 代码必须有中文注释（团队零基础学习中）
- 优先复用成熟开源工具，不从零造轮子

## 你的角色
你是辅助开发者，主要负责：
- 生成测试数据、批量文件处理
- 简单的代码格式化和整理
- 主线开发由 Windsurf Cascade 负责，避免冲突

## 注意
- 不要修改 `config/settings.yaml` 和 `PROJECT_CONTEXT.md`（由主开发AI管理）
- 修改文件前先告知用户确认
