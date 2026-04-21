# 影刃卫士 - 项目上下文记忆文件

> **用途**：换账号/换AI工具时，将本文件内容粘贴给AI即可恢复完整项目上下文。
> **最后更新**：2026-04-21 20:10

---

## 项目一句话

"影刃卫士"(ShadowBlade Guardian)——基于Qwen3-4B的AI Agent"影子技能"供应链静动态审计探针系统，以OpenClaw/ClawHub真实技能生态为审计对象。四川轻化工大学大创申报项目，校级/省级。

## 团队

- 3人，网络工程与安全专业，大模型零基础
- 硬件：3台笔记本，均配NVIDIA RTX 4060 Laptop GPU 8GB
- 开发环境：WSL2 + Ubuntu（详见下方开发环境章节）
- AI辅助开发：Windsurf (Claude/GPT) + Codex
- 导师支持：可提供云显卡资源用于模型微调
- 周期：2026.05 — 2026.12（8个月）

## 开发环境（已确认）

```
操作系统:   Windows, 1TB固态硬盘 (C盘300GB剩余~105GB, D盘602GB剩余~155GB)
WSL2:      Ubuntu (已安装, 位于C盘, 当前占用~8GB)
WSL用户名:  niezekai
GPU:       NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB (WSL2可见)
Python:    3.12.3 (WSL2内已安装)
Docker:    ❌ 未安装（后续需要安装，动态沙箱引擎要用）
```

## 文件路径约定

```
D:\大创聂泽铠\                            ← Windows D盘，存文档（Windsurf文档工作区）
├── 影刃卫士_大创申报书_v2.md              ← 正式申报书（当前版）
├── 影刃卫士_技术实施方案_v2.md            ← 技术开发指南（当前版）
├── 影刃卫士_大创申报书.md                 ← v1旧版，已弃用
├── 影刃卫士_技术实施方案.md               ← v1旧版，已弃用
├── PROJECT_CONTEXT.md                    ← 本文件（项目记忆）
└── .windsurfrules                        ← Windsurf工作区规则

/home/niezekai/shadowblade/               ← WSL2内部，存代码（Windsurf代码工作区）
├── PROJECT_CONTEXT.md                    ← 记忆副本（需手动同步）
├── .windsurfrules                        ← 规则副本
├── src/                                  ← 全部Python代码（待创建）
├── config/semgrep_rules/                 ← Semgrep自定义YAML规则
├── models/qwen3-4b-awq/                 ← Qwen3-4B量化模型
├── data/                                 ← 数据集
├── sandbox/                              ← Docker沙箱相关
└── tests/                                ← 测试

Windsurf打开WSL2工作区方法: File → Open Folder → \\wsl$\Ubuntu\home\niezekai\shadowblade
```

## 核心架构（v2.1，含Agent升级路径）

```
审计对象: OpenClaw ClawHub 13,000+ 真实技能（Hermes Agent等也共享此生态）
    ↓
数据接入层: ClawHub爬取 / Git监控 / API提交 / SKILL.md解析
    ↓
┌─────────────────────────┬──────────────────────────┐
│ 静态审计引擎（工具函数）    │ 动态审计引擎（工具函数）     │
│ L1: Semgrep自定义规则扫描  │ Docker沙箱隔离执行         │
│ L2: Bandit Python安全检查  │ mitmproxy HTTP(S)流量捕获  │
│ L3: pip-audit 依赖漏洞    │ watchdog 文件访问监控       │
│ L4: LLM Guard PI载荷检测  │ 蜜罐(Honeypot)诱饵数据注入  │
│ L5: Qwen3-4B 语义代码审查  │ 行为异常检测               │
├─────────────────────────┴──────────────────────────┤
│ AI研判决策引擎（两阶段演进）                            │
│                                                      │
│ 阶段1(M1-M4): 固定流水线 pipeline.py                  │
│   → 写死调用顺序: L1→L2→L3→L4→L5→动态→融合→评分       │
│                                                      │
│ 阶段2(M5+):  ReAct Agent 模式 agent.py  ★论文核心     │
│   → LLM自主决定: 看初步结果→选择下一个工具→迭代推理     │
│   → 底层工具函数与阶段1完全共用，只改顶层调度            │
│   → 论文实验: pipeline vs agent 对比，量化检出率提升     │
├────────────────────────────────────────────────────┤
│ 模型服务: vLLM(Qwen3-4B-AWQ) + ChromaDB + BGE-small  │
├────────────────────────────────────────────────────┤
│ 可视化: Streamlit 仪表盘                              │
└────────────────────────────────────────────────────┘
```

### 论文三大创新点（SCI Q2 / CCF-C~B 目标）
1. **Agent-as-Auditor**: LLM Agent自主编排安全审计工具链（ReAct模式），非固定流水线
2. **蜜罐诱捕检测**: 注入假凭据/假文件到沙箱，通过监控泄露行为检测数据窃密（T2威胁）
3. **多源证据融合信任评分**: 静态+动态+LLM三引擎结果的可解释融合评分模型

## 技术栈完整列表

```
语言:        Python 3.12 (WSL2内)
模型:        Qwen3-4B AWQ 4-bit量化 (~3-4GB显存)
推理框架:    vLLM (OpenAI兼容API, localhost:8000)
微调(可选):  LoRA via Unsloth (rank=16, alpha=32)
向量数据库:  ChromaDB (本地持久化)
嵌入模型:    BGE-small-zh-v1.5 (CPU运行,不占GPU)
后端:        FastAPI
前端:        Streamlit
容器:        Docker (WSL2 backend) ← 还未安装

--- 复用的开源安全工具 ---
静态规则扫描:  Semgrep (自定义YAML规则)
Python安全:    Bandit
依赖漏洞:      pip-audit + safety
PI检测:        LLM Guard (ProtectAI)
网络捕获:      mitmproxy (透明HTTP/S代理)
文件监控:      watchdog (Python库)
```

## 关键技术决策

| 决策 | 选择 | 否决的备选 | 原因 |
|------|------|-----------|------|
| 工程策略 | 复用成熟开源组件+聚焦核心创新 | 全部自研 | 零基础团队，避免重复造轮子 |
| 审计对象 | OpenClaw/ClawHub | 自建模拟生态 | 真实生态13K+技能，标准化SKILL.md |
| 基座模型 | Qwen3-4B AWQ 4-bit | Qwen3-1.5B/7B | 3-4GB显存适配4060；4B够用 |
| 静态扫描 | Semgrep+Bandit | 手写AST遍历器 | 写YAML规则即可，不用写Python |
| PI检测 | LLM Guard | 自己写正则 | ProtectAI专业维护 |
| 网络监控 | mitmproxy | tcpdump+scapy | 透明代理，Python API，自动解密HTTPS |
| 文件监控 | watchdog | strace | Python库，轻量，跨平台 |
| LoRA微调 | 可选增强 | 必做 | PE+RAG优先，效果不够再微调 |
| AI研判调度 | M5升级为ReAct Agent模式 | 一开始就做Agent | 需要先有底层工具函数才能让Agent编排 |
| 论文目标 | 冲SCI Q2 / CCF-C~B | 只发中文核心 | 选题新+Agent模式+蜜罐+信任评分=足够创新点 |

## 威胁模型（T1-T6）

- T1-供应链投毒：恶意代码注入正常技能
- T2-数据窃密：窃取Agent上下文敏感数据
- T3-提示词注入载荷：返回值中嵌入恶意Prompt
- T4-权限越级：请求超出声明范围的权限
- T5-触发式后门：条件触发恶意逻辑（如特定日期激活）
- T6-依赖链攻击：上游依赖含恶意代码（typosquatting等）

## 数据集来源（几乎全部现成）

| 用途 | 来源 | 说明 |
|------|------|------|
| 恶意样本 | Datadog malicious-software-packages-dataset | 22K+样本，含AI Skills类别，git clone即用 |
| 恶意补充 | Backstabbers-Knife-Collection, PyPI恶意包注册表 | GitHub下载 |
| 良性样本 | ClawHub直接爬取 | 一个爬虫脚本搞定 |
| RAG知识库 | NVD CVE JSON + MITRE CWE XML | 免费公开下载 |
| LoRA标注 | GPT-4o/Claude API批量生成 | 对现成样本自动标注审计结论 |
| 漏洞检测基准 | PrimeVul (ICSE 2025) | 可选参考 |

## 自主开发代码量约1,400行

| 模块 | 类型 | 估计行数 |
|------|------|---------|
| LLM语义审计 | ★核心创新 | ~200行 |
| 蜜罐机制 | ★核心创新 | ~200行 |
| AI综合研判+信任评分 | ★核心创新 | ~300行 |
| Semgrep/Bandit/LLM Guard/pip-audit调用 | 胶水代码 | ~150行 |
| mitmproxy插件+watchdog监控 | 胶水代码 | ~140行 |
| ClawHub爬虫+SKILL.md解析 | 工具脚本 | ~100行 |
| Docker沙箱管理 | 集成代码 | ~150行 |
| Streamlit仪表盘 | 前端 | ~200行 |

## 量化指标目标

- 静态检出率 ≥ 85%，误报率 ≤ 15%
- 动态识别率 ≥ 75%
- 联合检出率 ≥ 92%
- 单技能审计 ≤ 5分钟
- 批量验证 ≥ 1,000个ClawHub真实技能
- 系统可在单卡4060 8GB稳定运行

## 里程碑

- M1(W2): Qwen3-4B推理跑通 + Semgrep/Bandit/LLM Guard/mitmproxy/Docker全部安装验证
- M2(W4): 威胁模型白皮书 + 从Datadog数据集筛选样本 + Semgrep规则集v0.1(20+条)
- M3(W6): 静态引擎四层流水线v1.0可独立运行
- M4(W8): 动态引擎v1.0(Docker+mitmproxy+蜜罐)
- M5(W10): 三引擎联调，端到端pipeline跑通
- M6(W12): Streamlit仪表盘 + ClawHub 1000+技能批量审计
- M7(W20): 论文初稿
- M8(W32): 结题（论文投稿+软著+答辩）

## 预算

| 项目 | 金额 |
|------|------|
| AutoDL云GPU(LoRA微调+批量测试) | ¥2,000 |
| API调用(GPT-4o/Claude生成训练数据) | ¥1,000 |
| 论文版面费 | ¥1,500 |
| 软著申请 | ¥500 |
| 域名+存储+资料+差旅 | ¥2,000 |
| **合计** | **¥7,000** |

## 重要背景知识

- **OpenClaw**: MIT开源AI助理框架，ClawHub是其技能市场(clawhub.ai)，13,000+社区技能
- **Hermes Agent**: NousResearch开发的Agent框架，可通过openclaw-imports导入ClawHub技能
- **Skills**: Agent的扩展能力单元，由SKILL.md+代码文件组成，类比npm包
- **ClawHub技能被多平台共享**(OpenClaw+Hermes Agent+...)，审计成果有跨平台安全保护价值
- **Datadog GuardDog**: 开源工具，已积累22K+恶意软件包数据集，含AI Skills类别

## 成员分工

| 成员 | 角色 | 职责 |
|------|------|------|
| 成员A(负责人) | 系统架构+AI核心 | Qwen3-4B部署、RAG知识库、AI研判引擎、LoRA实验 |
| 成员B | 静态分析+数据 | 威胁建模、数据集、Semgrep规则、Bandit/pip-audit/LLM Guard集成 |
| 成员C | 动态分析+前端 | Docker沙箱、mitmproxy、蜜罐、watchdog、Streamlit |

## 对AI助手的指令

- 当前使用v2版文档（_v2.md后缀），v1已弃用
- 代码风格：Python 3.12，类型注解，Pydantic数据模型
- 代码必须有中文注释（团队零AI基础，解释要通俗）
- 优先使用成熟开源工具，不要从零造轮子
- LoRA微调为可选增强，优先Prompt Engineering + RAG
- 文档目录：`D:\大创聂泽铠\`（Windows）
- 代码目录：`/home/niezekai/shadowblade/`（WSL2 Ubuntu）
- Windsurf打开WSL2：`\\wsl$\Ubuntu\home\niezekai\shadowblade`
- 数据集优先用现成的（Datadog数据集等），减少手动构造工作

---

## 开发进度日志

> 每次重要操作后更新此节，确保换AI/换账号时进度不丢失。

### 2026-04-21 — 项目初始化

**已完成：**
1. ✅ 文档阶段完成（Windows端）：申报书v2 + 技术方案v2 已定稿
2. ✅ 切换到WSL2开发环境，Windsurf打开 `/home/niezekai/shadowblade/`
3. ✅ 创建完整项目目录结构：
   - `src/` 下6个子模块：static_engine, dynamic_engine, ai_engine, data_ingestion, api, dashboard
   - `config/semgrep_rules/` — Semgrep自定义规则目录
   - `models/qwen3-4b-awq/` — 模型存放目录
   - `data/{malicious,benign,rag_knowledge}/` — 数据集目录
   - `sandbox/`, `tests/`, `logs/`
   - 所有Python包目录已放置 `__init__.py`
4. ✅ 创建 `pyproject.toml` — 项目元信息 + pytest/ruff配置
5. ✅ 创建 `requirements.txt` — 完整Python依赖清单（含版本号和中文注释）
6. ✅ 创建 `config/settings.yaml` — 全局配置（模型、RAG、三引擎、端口、阈值等）
7. ✅ 创建 `.gitignore` — 排除模型/数据集/日志/缓存等大文件
8. ✅ 创建 `README.md` — 项目说明文档

9. ✅ 初始化Git仓库（main分支），完成首次commit

**下一步（待做）：**
- [ ] 创建Python虚拟环境 (.venv) 并安装基础依赖
- [ ] 安装Semgrep和LLM Guard（体积大，单独安装）
- [ ] 安装Docker（动态沙箱引擎需要）
- [ ] 下载Qwen3-4B-AWQ模型到 models/qwen3-4b-awq/
- [ ] 连接GitHub远程仓库（可选，需先在GitHub创建repo）
- [ ] 开始M1里程碑：Qwen3-4B推理跑通 + 各工具安装验证

**当前工作区文件清单：**
```
/home/niezekai/shadowblade/
├── .gitignore
├── .windsurfrules
├── PROJECT_CONTEXT.md          ← 本文件
├── README.md
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── semgrep_rules/          （空，待填充规则）
│   └── settings.yaml
├── src/
│   ├── static_engine/          （空，待开发）
│   ├── dynamic_engine/         （空，待开发）
│   ├── ai_engine/              （空，待开发）
│   ├── data_ingestion/         （空，待开发）
│   ├── api/                    （空，待开发）
│   └── dashboard/              （空，待开发）
├── models/qwen3-4b-awq/       （空，待下载模型）
├── data/{malicious,benign,rag_knowledge}/  （空，待获取数据）
├── sandbox/                    （空，待配置Docker）
├── tests/                      （空，待编写测试）
└── logs/                       （空，运行时生成）
```
