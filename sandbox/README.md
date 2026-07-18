# sandbox/ — 动态引擎沙箱目录

本目录**仅供影刃卫士动态审计引擎使用**，是 Docker 沙箱挂载/临时文件落地点。

## 用途

| 子目录 / 文件 | 用途 | 谁创建 |
|---|---|---|
| `sandbox/<sample-name>/` | 动态引擎执行某个 SKILL.md 时的临时挂载点 | 动态引擎运行时（M4 开发） |
| `sandbox/*.tar` | Docker 镜像导出文件（已在 `.gitignore`） | 手动 / CI |

## 写入边界

| 角色 | 可写吗 |
|---|---|
| Cascade（主开发） | ✅ 通过动态引擎代码间接写入临时文件 |
| Claude Code | ❌ 一般不需要 |
| **Hermes Agent** | ❌ **不允许**——Hermes 的工作区在项目外的 `/mnt/d/hermes_workspace/`，详见 `docs/hermes_setup.md` |

## 安全提示

- 本目录**不应**包含真实凭据、生产数据、未审核的恶意样本执行结果。
- 危险样本的实际执行必须在**网络隔离的 Docker 容器**内（M4 实现），不直接落到宿主 sandbox/。
- 提交前检查：`git status sandbox/` 确认没有意外加入二进制大文件。
