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

## 新型攻击手法（2026.04 新增）

### 隐藏评论注入 (Hidden-Comment Injection)
- 在 Markdown HTML 注释 `<!-- -->` 中嵌入恶意指令
- **人类审阅者在渲染后看不见，但 LLM 读取原始文本时会执行注释中的指令**
- 受影响模型: DeepSeek-V3.2, GLM-4.5-Air
- **本系统覆盖**: skill_parser 不解析 HTML 注释内容，此为检测盲区，需新增注释内容提取+审查

### 注意力劫持 (Attention Hijacking)
- **RouteGuard 论文（arXiv:2604.22888）核心发现**: 恶意 Skill 导致模型生成时将注意力从可信上下文转移到恶意 Skill 片段
- 投毒越靠前、通过 description 通道注入，注意力转移越强
- 本质上是"指令竞争"而非传统注入——良性 Skill 本身就是指令密集的，恶意指令混在其中难以从文本层面区分

### Agent-to-Agent 传播
- 攻击者在 ClawHub 刷排名（未认证 curl 即可刷下载量），恶意 Skill 被推到 #1
- **AI Agent 自动优先安装高下载量 Skill** → 无需人类干预的自主传播链
- Straiker 发现攻击者创建虚假 AI Agent 身份在 Moltbook 推广恶意技能

### 意图-载荷解耦 (SkillJect)
- SKILL.md 只写无害指令（如"运行 setup 脚本初始化环境"），真正恶意代码藏在辅助 .sh/.py 文件中
- 绕过原因: SKILL.md 不含显式恶意指令，LLM 安全对齐和静态分析均被绕过

### 多轮渐进式攻击 (SkillAttack 发现)
- SkillAttack（arXiv:2604.04989）自动化红队框架发现: **仅 ~24% 成功攻击出现在前 2 轮，~70% 出现在第 3-4 轮**
- **单轮安全评测严重低估真实风险**——Agent 风险暴露天然更像多轮交互式渗透
- 对本项目的启示: 沙箱多次执行策略（当前 3 次）方向正确，但可能需要更多轮次

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

## 前沿检测框架（学术，2026.04 新增）

> 以下框架均为学术成果，与影刃卫士方向高度相关。其中多项已开源，可作为论文 baseline 或技术参考。

### RouteGuard — 内部信号检测（2026.04.24，arXiv:2604.22888）
- **中科院计算所**，F1=**0.8834**（目前已知最高），恢复 90.51% 被词法筛查遗漏的 description 攻击
- 核心思路: 冻结模型骨干，检测 LLM 内部的**注意力转移**和**隐藏状态对齐**信号
- 不依赖文本分析，而是看模型"内部注意力被谁劫持了"
- 局限: 需要访问模型内部信号（冻结骨干），对 API 调用场景不适用
- **对本项目的启示**: 本地部署 Qwen3-4B 可访问内部信号，理论上可集成类似机制

### MalSkills — 神经符号推理（2026.03，arXiv:2603.27204）
- F1=**93%**，在 7 个注册表 **150,108 技能**中发现 **620 个恶意技能**（76 个此前未知）
- 构建 Skill Dependency Graph（技能依赖图），连接 artifacts、operations、operands 和 value flows
- 神经符号推理：符号解析提取安全敏感操作 + LLM 辅助语义分析
- **对本项目的启示**: 依赖图建模可补充当前的线性分析流水线，发现跨文件/跨依赖的隐藏攻击链

### SkillFortify — 形式化验证（2026.03，arXiv:2603.00195）
- **已开源**（GitHub: varun369/skillfortify），MIT 许可
- F1=**96.95%**，精度=**100%（零误报）**，约 2.5ms/技能，支持 22 个 Agent 框架
- SAT 依赖解析 + 抽象解释静态分析 + 能力沙箱约束证明
- 提供 `scan`、`verify`、`lock`、`trust`、`sbom`、`dashboard` 命令
- **局限**: 仅覆盖可执行代码，不处理自然语言指令
- **对本项目的启示**: 可与影刃卫士互补——SkillFortify 做代码层形式化验证，影刃卫士做 NL 层语义+动态检测

### SkillTester — 效用+安全双基准（2026.03，arXiv:2603.28815）
- **北京大学**，已部署 skilltester.ai
- 同时评估技能的**功能效用**和**安全性**（成对对比：bare LLM vs LLM+Skill）
- 独立安全探测套件
- **对本项目的启示**: 审计不应只看"有没有恶意"，还要看"功能是否正常"——双维度评估

### 腾讯朱雀 A.I.G（2026.04 开源，github.com/tencent/AI-Infra-Guard）
- 已扫描 **50,000+ ClawHub 技能**，74.6% 声明网络权限，29,196 个外链域名
- **攻击链组合分析**：不只看单个行为，而是看"哪些行为可以组合成完整攻击链"
- 联合腾讯云 EdgeOne 推出 ClawScan 安全体检工具
- **已开源**，可直接复用

### Overreach — 行为对齐基准（GitHub: agentglass/overreach）
- 在植入**蜜罐凭证**的检测环境中测试 AI Agent
- 四维评分：任务完成度、范围合规性、蜜罐抗性、注入抗性
- **与本项目的蜜罐诱捕模块直接对应**，可作为评估基准

## 开源工具生态（2026.04 新增）

| 工具 | 许可 | 亮点 | 对本项目的价值 |
|------|------|------|-------------|
| **AgentAuditKit** | MIT | 124规则/25模块，覆盖13个Agent平台，OWASP+MCP全覆盖，SARIF输出，tool pinning防rug pull | 可集成作为额外静态扫描模块 |
| **腾讯 A.I.G** | 开源 | 50K+技能扫描，攻击链组合分析，55个AI组件覆盖 | 可直接复用攻击链分析模块 |
| **SkillFortify** | MIT | 形式化验证，100%精度，2.5ms/技能，22框架 | 代码层形式化验证互补 |
| **SkillSieve** | 开源 | 三层框架，400样本基准，F1=0.800 | 已作为 baseline 参考 |
| **Overreach** | 开源 | 蜜罐凭证+行为对齐评估 | 可复用其蜜罐评估方法论 |
| **bawbel-scanner** | 开源 | CLI扫描器，覆盖 skills/MCP/prompts | 参考其规则设计 |
| **Malicious-SKILL.md Dataset** | 开源(GitHub) | 对抗变体研究数据集 | 扩充测试样本 |
| **SkillTester** | 部署 skilltester.ai | 效用+安全双基准 | 论文实验可参考其评估方法 |

## 数据集来源（更新）

| 用途 | 来源 | 说明 |
|------|------|------|
| 恶意样本 | Datadog malicious-software-packages-dataset | 22K+ 样本 |
| 恶意样本 ★ | ClawHavoc 真实样本 (Koi/Antiy) | 1,184 个 IOC |
| 恶意样本 ★ | Snyk ToxicSkills | 76 个恶意载荷 |
| 恶意样本 ★ | MalSkills 发现的未知恶意技能 | 620 个（76 个此前未知） |
| 恶意样本 ★ | Malicious-SKILL.md Adversarial Dataset | 对抗变体样本（GitHub开源） |
| 良性样本 | ClawHub 直接爬取 | 13K+ 技能 |
| RAG 知识库 | NVD CVE + MITRE CWE + OWASP AST10 | 免费公开 |
| 评估基准 ★ | Agent Security Bench (ASB, ICLR 2025) | 学术基准 |
| 评估基准 ★ | SkillSieve 标注基准 | 400 样本（89恶意+311良性） |
| 评估基准 ★ | SkillFortifyBench | 540 样本 |
| 评估基准 ★ | SKILL-INJECT Benchmark | 202 对注入任务 |

## 重要背景知识

- **OpenClaw**: MIT 开源 AI 助理框架，ClawHub 是其技能市场（13,000+ 技能）
- **Skills**: Agent 扩展能力单元，由 SKILL.md + 代码文件组成
- **ClawHub 技能被多平台共享**（OpenClaw + Hermes Agent + ...），审计成果有跨平台价值
- **2026.02**: OpenClaw + VirusTotal 合作，自动扫描所有发布技能（Gemini 驱动）
- **赛道现状（2026.04）**: 赛道爆发中。Permiso SandyClaw（动态沙箱）、SkillSieve（学术三层）、SafeSkill（商业4引擎）、SkillProbe（多Agent审计）、AgentAuditKit（124规则开源）、腾讯A.I.G（开源50K+扫描）、RouteGuard（内部信号检测 F1=0.88）、MalSkills（神经符号 F1=0.93）、SkillFortify（形式化验证 100%精度）、DDIPE（新型攻击）、隐藏评论注入（新型攻击）

### 关键数据点（2026.04 更新）

| 数据 | 来源 |
|------|------|
| ClawHub 技能总数 ~50,000 | 腾讯朱雀 |
| 开发者 15,427 名，Top20 产 12.9% | 腾讯朱雀 |
| 74.6% 技能声明网络权限 | 腾讯朱雀 |
| 29,196 个外链域名 | 腾讯朱雀 |
| 恶意技能 ~620（7个注册表） | MalSkills |
| 30 个 MCP CVE 在 60 天内爆出 | 行业统计 |
| ClawHavoc 损失: 247,693 安装 + $2.3M 加密货币 | 行业统计 |

### 对本项目的可操作建议（辅助AI 2026-04-30）

1. **比赛/论文层面**:
   - RouteGuard、MalSkills、SkillFortify 均可作为论文 baseline 对比
   - 用 SkillSieve 的 400 样本基准 + SkillFortifyBench 540 样本扩充评估
   - SkillAttack 多轮测试结论支持我们的"多次沙箱执行"设计决策

2. **技术层面（可直接复用）**:
   - 腾讯 A.I.G 已开源 → 研究其攻击链组合分析模块
   - AgentAuditKit MIT 许可 → 评估是否可作为额外静态扫描层
   - Overreach 蜜罐评估方法论 → 优化我们的 D4 蜜罐模块设计

3. **需新增的检测能力**:
   - HTML 注释内容提取 + 审查（当前 skill_parser 不解析注释）
   - 多轮沙箱执行轮次从 3 次增加到 5 次（SkillAttack 建议）
   - 跨文件依赖图建模（MalSkills 思路）
