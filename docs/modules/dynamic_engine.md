# 动态审计引擎

> 状态：待开发（M4 里程碑）

## 计划功能

| 模块 | 工具 | 作用 |
|------|------|------|
| D1 | Docker | 沙箱隔离执行，限制 CPU/内存/网络 |
| D2 | mitmproxy | HTTP(S) 流量捕获 + WebSocket C2 检测 |
| D3 | watchdog | 文件系统监控 + 身份文件保护（SOUL.md/MEMORY.md） |
| D4 | 自研 | 蜜罐诱饵注入（假凭据 + 假文件 + 假 API Key） |
| D5 | 自研 | 行为异常检测（网络外联、Shell 调用模式） |

## 关键设计决策

- 沙箱用 `libfaketime` 伪造时间偏移 48h，检测延迟激活恶意代码
- Docker 配置：`--network none`（默认禁止网络）或通过 mitmproxy 代理
- 多次执行策略：正常执行 → 伪造 48h 后再执行 → 对比行为差异
