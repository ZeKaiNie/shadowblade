# 系统架构

## 核心架构（v3，对齐 OWASP AST10）

```
审计对象: ClawHub技能（SKILL.md + 代码文件 + 依赖 + 元数据）
    ↓
数据接入层: ClawHub爬取 / Git监控 / SKILL.md+SOUL.md+MEMORY.md解析
    ↓
┌──────────────────────────────┬──────────────────────────────┐
│ 静态审计引擎                    │ 动态审计引擎                    │
│                                │                                │
│ S1: SKILL.md语义分析 ★核心     │ D1: Docker沙箱隔离执行          │
│   → 规则快筛 + LLM语义理解     │ D2: mitmproxy HTTP(S)流量捕获   │
│                                │   → WebSocket C2连接检测         │
│ S2: Semgrep自定义规则扫描       │ D3: watchdog 文件系统监控        │
│ S3: Bandit Python安全检查       │   → 身份文件保护(SOUL/MEMORY)    │
│ S4: 依赖安全扫描                │ D4: 蜜罐诱饵数据注入             │
│   → pip-audit + typosquatting  │ D5: 行为异常检测                 │
│ S5: LLM Guard PI载荷检测       │                                │
│ S6: 权限清单验证               │                                │
├──────────────────────────────┴──────────────────────────────┤
│ AI研判决策引擎（两阶段演进）                                     │
│ 阶段1(M1-M4): 固定流水线 pipeline.py                           │
│ 阶段2(M5+):  ReAct Agent 模式 agent.py ★论文核心              │
├───────────────────────────────────────────────────────────────┤
│ 模型服务（可插拔，LiteLLM统一接口）                               │
│ 本地: vLLM(Qwen3-4B-AWQ)  云端: DeepSeek/GPT-4o/Claude       │
│ RAG: ChromaDB + BGE-small                                     │
├───────────────────────────────────────────────────────────────┤
│ 可视化: Streamlit 仪表盘                                        │
└───────────────────────────────────────────────────────────────┘
```

## 技术栈

```
语言:        Python 3.12 (WSL2)
模型(默认):  Qwen3-4B AWQ 4-bit量化 (~3-4GB显存)
推理框架:    vLLM (OpenAI兼容API, localhost:8000)
模型网关:    LiteLLM (统一接口，一行配置切换本地/云端)
向量数据库:  ChromaDB (本地持久化)
嵌入模型:    BGE-small-zh-v1.5 (CPU运行)
后端:        FastAPI
前端:        Streamlit
容器:        Docker (WSL2 backend)

--- 复用的开源安全工具 ---
静态规则:    Semgrep (自定义YAML规则)
Python安全:  Bandit
依赖漏洞:    pip-audit + safety
PI检测:      LLM Guard (ProtectAI)
网络捕获:    mitmproxy (透明HTTP/S代理)
文件监控:    watchdog (Python库)
时间伪造:    libfaketime (沙箱内伪造时间偏移48h)
```

## OWASP AST10 威胁模型映射

| AST | 风险 | 本系统覆盖 |
|-----|------|-----------|
| AST01 ★ | 恶意技能 | S1+S2+D3+D4 |
| AST02 ★ | 供应链攻陷 | S4(typosquatting) |
| AST03 ★ | 过度授权 | S6(权限清单验证) |
| AST04 | 不安全元数据 | S1(语义分析) |
| AST05 | 不安全反序列化 | S2(Semgrep规则) |
| AST06 ★ | 弱隔离 | D1(Docker沙箱) |
| AST07 ★ | 依赖问题 | S4(pip-audit+相似度) |
| AST08 | 缺乏溯源 | 审计结果记录 |
| AST09 | 缺乏治理 | S6+信任评分 |
| AST10 | 缺乏风险分级 | 信任评分+risk_tier |

## 扩展威胁覆盖（超出 OWASP AST10）

| 威胁 | 风险 | 本系统覆盖 |
|------|------|-----------|
| **DDIPE** ★ | 文档驱动隐式载荷执行（代码示例中嵌入恶意逻辑） | S1(语义分析检测代码与功能不一致) |
| 延迟激活 | 代码前N次正常执行，等待条件后激活恶意行为 | D1+libfaketime(伪造48h时间偏移) |
| Unicode 隐写 | Tags区(U+E0000-U+E007F)隐藏指令 | S1(skill_parser ASCII smuggling检测) |

## 论文五大创新点（2026.04 更新）

1. **SKILL.md 语义分析**: LLM 检测自然语言层恶意指令，包括 DDIPE 隐式载荷（代码示例与声明功能的一致性检验）
2. **Agent-as-Auditor**: ReAct 模式自主编排工具链（SkillSieve 为固定流水线，无自主推理）
3. **蜜罐诱捕检测**: 假凭据注入 + 泄露监控（所有竞品均无此能力）
4. **多源证据融合信任评分**: 静态+动态+LLM 可解释融合（含 libfaketime 延迟激活检测）
5. **模型可插拔+多维对比实验**: LiteLLM 统一接口，三组对比（pipeline vs agent、小模型 vs 大模型、本地 vs 云端）

## 项目定位

**安装前审计系统**：在用户安装/运行技能之前，在隔离环境中完成全部审计。沙箱内用 libfaketime 伪造时间偏移 48h，检测延迟激活恶意代码。

**核心差异化（2026.04 更新）**：SandyClaw 有动态沙箱但无蜜罐诱捕和 LLM 语义分析；SkillSieve 有三层检测但无动态执行；SafeSkill 有四引擎但无 Agent 自主推理。**影刃卫士是唯一同时覆盖"静态语义分析 + 动态沙箱 + 蜜罐诱捕 + Agent 自主推理"四合一完整闭环的系统**，且独有的 libfaketime 时间偏移可检测延迟激活恶意代码，独有的蜜罐诱捕可主动发现数据窃取行为。
