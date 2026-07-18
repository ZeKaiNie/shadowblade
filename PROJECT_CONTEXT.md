# 影刃卫士 - 项目上下文（精简版）

> ⚠️ 本文件已于 2026-07-18 精简重写。旧的 460 行详细规划（含大量未核实数据、过时的
> 双 AI 分工、WSL 本地路径、"SCI Q2/CCF-B"等激进目标）已废弃。
> **知识库入口是 `docs/INDEX.md`**；整体重构与论文规划见 `docs/planning/`。

## 一句话

**影刃卫士（ShadowBlade Guardian）**——面向 AI Agent 技能供应链的安全审计系统。
核心思路是把陌生技能放进**布满蜜罐诱饵的隔离沙箱**里真实执行，用运行时行为监控
（Python 审计钩子 + 规划中的内核级监控）捕获它对假凭据/身份文件的窃取与外传，形成
"抓现行"的确凿证据，再结合静态扫描与 LLM 语义研判做可解释的综合风险评分。

## 真实现状（2026-07）

- ✅ **静态引擎**：SKILL.md 解析 + Semgrep/Bandit/pip-audit + 隐写检测 + LLM 语义研判 + 风险评分。
- 🟡 **动态引擎**：最小闭环已落地（Docker `--network none` 沙箱 + 蜜罐随机标记 + `sys.addaudithook`
  行为探针 + 研判打分），已接入 `audit_skill(enable_dynamic=True)` 综合评分。
- 🟡 **AI 研判**：RAG（ChromaDB + BGE-small）/ 信任评分有骨架。
- ⬜ **未做**：数据集 + 评测框架、内核级监控(eBPF/seccomp)、libfaketime、多次执行对比、
  非 Python 载荷、数据接入、FastAPI、Streamlit。
- ❌ **已作废**：此前文档中"15 样本 / 100% 检出 / 0% 误报"等指标为编造，不得引用。

## 团队 / 硬件 / 环境

- 3 人，四川轻化工大学网络工程与安全专业，大模型基础薄。
- 硬件：笔记本 + RTX 4060 Laptop 8GB；导师可提供云 GPU。
- 开发环境：WSL2 + Ubuntu；本地模型 Qwen3-4B AWQ（vLLM），云端模型经 LiteLLM 可切换（对比实验用）。
- 代码仓库：https://github.com/ZeKaiNie/shadowblade

## 论文目标（现实定级）

- 现实可及：**CCF-C 会议 / 中文核心 / SCI Q3–Q2**。
- 短期不现实：CCF-A/B 顶会、SCI Q1。
- 关键：能否发表取决于**数据集 + baseline 对照 + 消融 + 抗规避评估**这套实证严谨度，
  而非功能数量。详见 `docs/planning/影刃卫士_CCFC论文可行性与排期优化.md`。

## 核心差异化（论文卖点）

1. per-run 随机蜜罐标记 → 外传取证（确定性、可复现、不依赖 LLM）——headline。
2. 分层行为监控（Python 审计钩子 + 内核 eBPF/seccomp），覆盖非 Python/原生载荷、抗规避。
3. Agent 身份/记忆持久化后门检测（SOUL.md/MEMORY.md/AGENTS.md）。
4. 抗规避评估（时间炸弹 via libfaketime、沙箱探测）。
5. （次要）静态 + 多模型 LLM 语义研判作对照与融合，不作主创新。

## 下一步优先级

**P0（论文生命线）**：攻击分类学 + 数百级标注数据集 + 一键评测框架（P/R/F1/FPR + baseline/消融）。
之后才是内核级监控、抗规避、多模型对比。FastAPI/Streamlit/mitmproxy 属 demo 级，非关键路径。
完整排期见 `docs/planning/影刃卫士_v2架构重构设计.md`。
