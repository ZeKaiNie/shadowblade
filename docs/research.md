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

## 竞品对比

| | Snyk ToxicSkills | 微软 Governance Toolkit | ClawSecure | Cisco DefenseClaw | **影刃卫士** |
|--|--|--|--|--|--|
| 性质 | 一次性报告 | 运行时治理 | SaaS 扫描器 | 开源工具集 | **安装前自动审计** |
| SKILL.md 语义分析 | 有限 | ❌ | ✅ | ✅ LLM-as-Judge | ✅ LLM 自动化 |
| 动态沙箱 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 蜜罐诱捕 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 网络/文件监控 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Agent 自主推理 | ❌ | ❌ | ❌ | ❌ | ✅ ReAct |

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
