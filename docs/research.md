# 背景研究 & 竞品分析

## ClawHavoc 攻击案例（2026.01-02，论文 Motivation 核心素材）

- **规模**: 1,184 个恶意技能，12 个发布者账号
- **攻击手法**:
  - SKILL.md 自然语言指示 Agent 读取 SSH 密钥并外传
  - 代码层投递 AMOS 窃密木马（macOS 加密钱包、浏览器密码）
  - 向 SOUL.md/MEMORY.md 写入后门指令（卸载后持久化）
  - WebSocket 长连接 C2（91.92.242[.]30）
  - 品牌冒充（伪装 Google、Solana、YouTube 等）
- **已知攻击者**: zaycv（40+自动化生成）、Aslaep123（加密货币主题）、aztr0nutzs（NET_NiNjA.v1.2 仓库）
- **影响**: Top7 技能中 5 个是恶意软件，约 300,000 用户受影响
- **引用**: Koi Security, Snyk ToxicSkills, Antiy CERT, Trend Micro, OWASP AST10

## Snyk ToxicSkills 研究

- 36% 技能存在安全缺陷，1,467 个漏洞载荷
- 攻击类型: 外部恶意分发、混淆数据外泄、安全禁用、提示词注入
- ASCII 隐写（Tags 区 U+E0000-U+E007F）隐藏恶意指令
- 密码保护 ZIP 文件逃避自动扫描

## DDIPE 新型攻击（2026.04，arXiv:2604.03081）

- **Document-Driven Implicit Payload Execution**: 攻击者在 SKILL.md 代码示例中嵌入恶意逻辑
- Agent 执行正常任务时"自然地"复现并执行这些示例代码——无需显式恶意指令
- 绕过模型层安全对齐（无非明确恶意命令）、绕过框架层沙箱（Agent 自己生成并执行的代码）
- 11.6%–33.5% 绕过率（4框架×5模型），2.5% 同时绕过静态检测和模型对齐
- **本系统应对**: S1 LLM 语义分析可检测"代码示例与声明功能不一致"，但需针对性设计 Prompt

## 竞品对比（2026-04 更新）

> **赛道爆发中**：2026年3-4月间出现多个直接竞品，验证了选题判断。各竞品在不同维度各有侧重，影刃卫士的核心差异化在于**四合一完整闭环**（静态语义 + 动态沙箱 + 蜜罐诱捕 + Agent 自主推理），而非单一维度优势。

### 全景对比

| | Snyk ToxicSkills | 微软 Governance Toolkit | ClawSecure | Cisco DefenseClaw | Permiso SandyClaw | SkillSieve (学术) | SafeSkill 微步 | **影刃卫士** |
|--|--|--|--|--|--|--|--|--|
| 性质 | 一次性报告 | 运行时治理 | SaaS扫描器 | 开源工具集 | 商业沙箱 | 学术框架 | 商业平台 | **学术+开源** |
| 上线时间 | 2026.02 | 2026.04 | 2025 | 2026.02 | 2026.04 | 2026.04(arXiv) | 2026.03 | 2026.05(计划) |
| SKILL.md 语义分析 | 有限 | ❌ | ✅ | ✅ | ❌ | ✅ SSD四子任务 | ✅ LLM深度 | ✅ LLM + RAG |
| 静态代码扫描 | ✅ | ❌ | ✅ | ✅ YARA+Semgrep | ❌ | ✅ Regex+AST | ✅ 多层静态 | ✅ Semgrep+Bandit |
| **动态沙箱** | ❌ | ❌ | ❌ | ❌ | ✅ Docker | ❌ | ❌(仅PE沙箱) | ✅ Docker+libfaketime |
| **蜜罐诱捕** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 假凭据+假文件 |
| **时间伪造** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ libfaketime 48h |
| 网络/文件监控 | ❌ | ❌ | ❌ | ❌ | ✅ SSL拦截 | ❌ | ❌ | ✅ mitmproxy+watchdog |
| Agent 自主推理 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ ReAct |
| 多LLM陪审团 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 三模型辩论 | ❌ | ❌ |
| URL主动探测 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌(计划中) |
| 模型可插拔 | N/A | N/A | N/A | N/A | N/A | ❌ | N/A | ✅ LiteLLM |
| 消费级GPU | N/A | N/A | N/A | ✅ | N/A | ✅ $440 ARM | N/A | ✅ 4060 8GB |

### 各竞品要点

- **Permiso SandyClaw**（2026.04.02）：首个商用动态沙箱，SSL流量解密 + Sigma/YARA/Nova/Snort多引擎，**但无蜜罐、无LLM语义分析、无自主推理**
- **SkillSieve**（2026.04.08，arXiv）：三层学术框架（静态筛→LLM语义→多LLM陪审），F1=0.800，**已开源代码+数据+基准**。架构与影刃卫士高度重合但无动态引擎
- **微步 SafeSkill**（2026.03）：4引擎商业产品，已扫描30万+技能，含URL主动探测+PE沙箱，**但无通用动态沙箱、无蜜罐、无Agent推理**
- **SkillProbe**（2026.03.22，arXiv）：多Agent协作审计，关注组合风险模拟，**2,500真实技能评估**
- **DDIPE 攻击**（2026.04，arXiv）：新型文档隐式载荷执行攻击，代码示例中嵌入恶意逻辑，11.6%-33.5%绕过率

## 数据集来源

| 用途 | 来源 | 说明 |
|------|------|------|
| 恶意样本 | Datadog malicious-software-packages-dataset | 22K+ 样本 |
| 恶意样本 ★ | ClawHavoc 真实样本 (Koi/Antiy) | 1,184 个 IOC |
| 恶意样本 ★ | Snyk ToxicSkills | 76 个恶意载荷 |
| 良性样本 | ClawHub 直接爬取 | 13K+ 技能 |
| RAG 知识库 | NVD CVE + MITRE CWE + OWASP AST10 | 免费公开 |
| 评估基准 ★ | Agent Security Bench (ASB, ICLR 2025) | 学术基准 |

## 重要背景知识

- **OpenClaw**: MIT 开源 AI 助理框架，ClawHub 是其技能市场（13,000+ 技能）
- **Skills**: Agent 扩展能力单元，由 SKILL.md + 代码文件组成
- **ClawHub 技能被多平台共享**（OpenClaw + Hermes Agent + ...），审计成果有跨平台价值
- **2026.02**: OpenClaw + VirusTotal 合作，自动扫描所有发布技能（Gemini 驱动）
- **赛道现状（2026.04）**: 多个竞品集中出现，赛道爆发前夜。Permiso SandyClaw（动态沙箱）、SkillSieve（学术三层框架）、微步 SafeSkill（商业4引擎）、SkillProbe（多Agent审计）、DDIPE（新型攻击向量）
