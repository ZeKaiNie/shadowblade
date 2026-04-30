# 关键技术决策

> 记录"为什么选 X 不选 Y"，避免反复讨论已定事项

| 决策 | 选择 | 否决的备选 | 原因 |
|------|------|-----------|------|
| 工程策略 | 复用成熟开源组件 | 全部自研 | 零基础团队，避免造轮子 |
| 审计对象 | OpenClaw/ClawHub | 自建模拟生态 | 真实生态 13K+技能 |
| 基座模型 | Qwen3-4B AWQ 4-bit | Qwen3-1.5B/7B | 3-4GB 显存适配 4060 |
| 静态扫描 | Semgrep+Bandit | 手写 AST 遍历器 | 写 YAML 规则即可 |
| PI 检测 | LLM Guard | 自己写正则 | ProtectAI 专业维护 |
| 网络监控 | mitmproxy | tcpdump+scapy | Python API，自动解密 HTTPS |
| 文件监控 | watchdog | strace | Python 库，轻量 |
| LoRA 微调 | 可选增强 | 必做 | PE+RAG 优先，效果不够再微调 |
| AI 调度 | M5 升级为 ReAct | 一开始就做 Agent | 需先有底层工具函数 |
| 模型网关 | LiteLLM | 写死 vLLM 调用 | 一行配置切模型 |
| 知识库 | ChromaDB+BGE-small | LLM Wiki | 需溯源引用，RAG 更适合 |
| 论文目标 | SCI Q2 / CCF-C~B | 只发中文核心 | 5 个创新点足够支撑 |
| Prompt 设计 | 四子任务并行（SSD） | 单一综合 Prompt | SkillSieve 验证 SSD 提升 F1 0.746→0.800 |
| 差异化定位 | 四合一闭环 | 单一维度突破 | SandyClaw/SkillSieve/SafeSkill 各占一维 |

## 重要约束

- **ClawHavoc 原始恶意 SKILL.md 已从 ClawHub 下架**，需基于公开报告构造合成样本
- Snyk toxicskills-goof 仓库有 4 个真实恶意 SKILL.md 演示样本
- Datadog 数据集是 npm/PyPI 恶意包（非 ClawHub），代码层分析可用
