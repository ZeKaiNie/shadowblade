# 动态审计引擎

> 状态：**最小闭环已实现**（Docker 沙箱 + 蜜罐 + 行为监控 + 研判），M4 其余能力（mitmproxy/libfaketime/多次执行）待补

## 已实现（v0.1 最小闭环）

在带蜜罐诱饵的隔离沙箱里真实执行技能代码，用 CPython 审计钩子（`sys.addaudithook`）
捕获运行时行为，再研判风险。

| 文件 | 作用 |
|------|------|
| `src/dynamic_engine/honeypot.py` | 蜜罐：生成带唯一随机标记的假凭据（env + 文件），布置到沙箱 |
| `src/dynamic_engine/harness.py` | 沙箱内探针：布现场 + 审计钩子监控 open/socket/subprocess/exec + 输出行为清单 |
| `src/dynamic_engine/sandbox.py` | 执行器：Docker 后端（`--network none` 断网、限内存/CPU/pids、跑完即焚）+ 子进程兜底（默认关，不隔离仅供本地测试） |
| `src/dynamic_engine/monitor.py` | 研判：把行为清单折算成 0-1 动态风险分 + 可读结论 |
| `src/dynamic_engine/pipeline.py` | 主入口 `audit_dynamic()`：布蜜罐 → 进沙箱跑 → 监控研判 |
| `src/dynamic_engine/models.py` | 数据模型：BehaviorEvent / SandboxRunResult / DynamicAuditResult |

### 检测判据（从强到弱）
1. **蜜罐命中**：假凭据的随机标记出现在网络/子进程参数里 → 数据外传铁证（+0.70）
2. **身份文件篡改**：写 SOUL.md/MEMORY.md/AGENTS.md → 持久化后门（+0.35）
3. **连已知恶意域名/IP**：ClawHavoc IOC + 匿名外传服务（+0.30）
4. **读诱饵 + 网络外联**：凭据窃取典型组合（+0.40）
5. **子进程远程脚本**：curl|bash 等（+0.30）

### 已接入综合评分
`static_engine/pipeline.audit_skill(enable_dynamic=True)` 会调用动态引擎，
综合评分权重对齐 `settings.yaml`：静态 0.4 / 动态 0.35 / LLM 0.25（未启用引擎自动剔除并归一化）。
沙箱未跑起来（无 Docker 且未允许子进程）时 `dynamic_enabled=False`，优雅降级不影响静态/LLM。

### 用法
```python
from src.dynamic_engine.pipeline import audit_dynamic
res = audit_dynamic(code_blocks, code_languages, backend="docker")  # 默认 auto
print(res.risk_score, res.honeypot_triggered, res.finding_texts)
```

## 待补（M4 剩余）

| 模块 | 工具 | 作用 |
|------|------|------|
| D2 | mitmproxy | HTTP(S) 流量解密 + WebSocket C2 检测（当前用审计钩子捕获网络目标，未解密 body） |
| libfaketime | LD_PRELOAD | 伪造时间偏移 48h，触发延迟激活恶意代码 |
| 多次执行 | 自研 | 正常执行 → 伪造 48h 后再执行 → 对比行为差异 |
| 非 Python 载荷 | 自研 | 当前沙箱仅执行 Python 代码块，bash/node 待扩展 |

## 关键设计决策

- **审计钩子而非 strace**：`sys.addaudithook` 拿到 open/socket.connect/subprocess.Popen
  的真实参数，轻量、跨平台、可判断蜜罐标记是否被外发，无需 root。
- **Docker `--network none`**：默认断网，恶意代码即使想外传也发不出去，但外传**尝试**
  （urllib.Request 的 URL/body）在真正发包前就被审计钩子记下，实现"抓现行不放毒"。
- **子进程后端不隔离**：仅作无 Docker 时的兜底，必须显式 `allow_unsafe_subprocess=True`，
  严禁用它跑真实恶意样本。
