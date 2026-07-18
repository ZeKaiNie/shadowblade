# 开发进度

> 最后更新：2026-05-10（**Hermes 暂缓**，焦点回 M2 收尾 + M3 静态引擎；XIAOMI_API_KEY 已要求用户轮换）

## 当前状态：M2 → M3 过渡（静态全链路打通）

### 2026-05-10 决定：Hermes 暂缓 ⏸️ + 切回 M3 选项 B（LLM 接入流水线）

**两个决定**：
1. **Hermes Agent 暂缓**——先放下，专注项目本体。Hermes 已安装 + provider 配好（D 盘原位保留，以后随时可继续）。
2. **下一步选定 M3 选项 B**：把 MiMo LLM 接入 `pipeline.audit_skill()`，跑 15 样本（10 恶意 + 5 正常）拿**联合检出率/误报率**第一手数据。

**Hermes 保留的资产**（D 盘原位，未来恢复时用）：
- 安装：`/mnt/d/hermes_data/hermes_home/hermes-agent/`
- 配置：`config.yaml` (mimo-v2.5-pro + xiaomi)、`.env`（旧 key 已要求轮换 → 即将清空）、`models_dev_cache.json` (1.9MB)
- 工作区：`/mnt/d/hermes_workspace/`、cache 软链
- 边界：`~/.config/hermes/WORKSPACE.md`

#### 选项 B 已完成的诊断（今天 15:09-15:18）

- ✅ `settings.yaml.llm.mimo` 配置完整：`api_base=https://token-plan-cn.xiaomimimo.com/v1`、`model=mimo-v2.5-pro`、`api_key_env=MIMO_API_KEY`
- ✅ `src/ai_engine/llm_client.py:load_llm_config("mimo")` 自动从 `os.getenv("MIMO_API_KEY")` 读 key 并封装为 `LLMConfig`
- ✅ `src/static_engine/pipeline.py:audit_skill(enable_llm=True, llm_api_base, llm_model, llm_api_key, ...)` 已有 LLM 接入路径（pipeline.py:288-378）
- ✅ `RiskLevel` 5 档阈值：≥0.20=LOW、≥0.40=MEDIUM、≥0.60=HIGH、≥0.80=CRITICAL（pipeline.py:224-243）—— **检出阈值用 ≥ MEDIUM**
- ✅ `tests/test_real_samples.py` **只测 S1+S2+S3 静态部分**，没用 `audit_skill` 主入口、也没接 LLM → 这是 B 的真正缺口
- ✅ `tests/` 已有 100 测试可 collected
- ❌ `MIMO_API_KEY` 环境变量**未设**（既不在 ~/.bashrc，也不在当前 shell，项目根无 .env）— **B 任务的卡点**

#### 选项 B 待做（按顺序，新会话直接从这里接）

1. **【用户】到 [token-plan 控制台](https://platform.xiaomimimo.com)** 禁用旧 key（`tp-cc7bg...` 已暴露）+ 生成新 key
2. **【用户】在 WSL 原生终端**（不通过 IDE，避免抓取）跑：
   ```bash
   echo 'export MIMO_API_KEY="<新-key>"' >> ~/.bashrc
   source ~/.bashrc
   echo "MIMO_API_KEY length=${#MIMO_API_KEY}"   # 验证只看长度
   ```
3. **【Cascade】用 `sed` 清空 `$HERMES_HOME/.env` 里的旧 key 字段**（一行命令）：
   ```bash
   printf 'XIAOMI_API_KEY=\nXIAOMI_BASE_URL=\n' > /mnt/d/hermes_data/hermes_home/.env
   ```
4. **【Cascade】写 `tests/test_real_samples_llm.py`**：
   - 文件级 skip：`MIMO_API_KEY` 未设时整个文件 skip
   - `@pytest.mark.integration` 标记（默认不跑，避免常规 pytest 调云端）
   - 用 `audit_skill(enable_llm=True, ...)` 走完整流水线，参数从 `load_llm_config("mimo")` 拿
   - 测试函数：单样本硬断言（恶意 ≥ MEDIUM、良性 ≤ LOW）+ 聚合指标软警告（按 user_rules 不为刷分调参原则，仅打印）
   - 打印每样本 `static_risk` vs `final_risk`，便于看 LLM 加成
5. **【Cascade】跑测试**：`bash -lc 'source ~/.bashrc && pytest tests/test_real_samples_llm.py -v -m integration'`（注意：run_command 的 shell 默认不加载 .bashrc，要用 `bash -lc`）
6. **【Cascade】记录联合指标到 progress.md** § 量化指标表
7. （可选 b-4）给 `audit_skill` 加个接受 `LLMConfig` 的语义糖，免去手动拆 `api_base/model/api_key`

#### 卡点 / 中断原因

**2026-05-10 15:18 用户额度用完，切换账号继续**。新会话恢复指引见下面 §「新会话接续指南」。

---

## 新会话接续指南（任意账号切换后用）

**新 Cascade 会话第一步**：读 `docs/INDEX.md` → 读 `docs/progress.md` 第 7-50 行（本节）。

**当前主线**：M3 选项 B（LLM 接入 pipeline）。**当前卡点**：用户在 token-plan 轮换 key 中。

**接续动作分支**：
- 如果用户**已设好 `MIMO_API_KEY`** → 跳到选项 B 待做的第 3-6 步执行
- 如果用户**还没轮换** → 提醒他完成第 1-2 步（不催，问一句进度即可）
- 如果用户**改主意切到选项 A 或 C** → 看 5/10 上一版 todo 里的 next-1 / next-3

**绝对不要做的事**：
- ❌ 重启 Hermes 配置流程（已暂缓）
- ❌ 改 `tests/test_real_samples.py`（保留原文件，要写**新**文件 `test_real_samples_llm.py`）
- ❌ 改 `pipeline.audit_skill` 签名（除非做可选 b-4）
- ❌ 用 nano 打开任何含 key 的文件（IDE 会抓内容，5/9 已踩过坑）

**未来重启 Hermes 时的接续点**：见 5/9 晚那一节的待办（方案 A 搬 venv 到 C 盘 → 验证连通 → §2.5/§2.4/§3）

---

### 2026-05-09 晚 Hermes MiMo provider 配置完成 ✅（已暂缓，待复用）

**最终结果**：`config.yaml` 写入 `model.default=mimo-v2.5-pro` + `provider=xiaomi`；`.env` 保存 `XIAOMI_API_KEY` + `XIAOMI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1`；`models_dev_cache.json` 1.9MB 已缓存。

**关键发现 & 学习**：

1. **Hermes 实际行为 ≠ 手册 §2.2**：Hermes 内置了 Xiaomi MiMo 预设 provider，硬编码变量名为 `XIAOMI_API_KEY`（不是手册写的 `MIMO_API_KEY`）；.env 路径是 `$HERMES_HOME/.env` 而非 `~/.hermes/.env`（仅当 `HERMES_HOME` 未设时才是后者）。**手册 §2.2 下次要修**。
2. **Base URL 默认值陷阱**：Hermes 默认值是 `https://api.xiaomimimo.com/v1`，但 token-plan 用户（key 前缀 `tp-`）**必须手动输** `https://token-plan-cn.xiaomimimo.com/v1`，否则 401。
3. **models.dev 拉模型 catalog 可能卡 15s**：源码 `agent/models_dev.py:226` 有 `timeout=15` + 三层 fallback（network → disk cache → curated list）。**不要 Ctrl+C**，否则 `KeyboardInterrupt` 不被 `except Exception` 吞掉，整个进程崩。第一次跑成功后会落盘 `models_dev_cache.json`，后续启动不再联网。
4. **启动慢根因：D 盘 9P 协议**：`hermes --version` 在 D 盘 venv 要 **15 秒**（对比 C 盘 ext4 的 Python 空启动 38 ms）。venv 839 MB、413 个包都在 `/mnt/d/hermes_data/hermes_home/hermes-agent/venv/`，跨 9P 协议 import 奇慢。→ **方案 A：搬 venv + 源码到 C 盘 `~/hermes-agent/`，数据保留 D 盘**。一次性 C 盘净增 ~1.2 GB，之后启动降到 1-2 秒。明天执行。

**【⚠️ 安全事件】**：5/9 晚指导用户时让用户 `nano $HERMES_HOME/.env` 看 key，但 IDE 抓取了 nano 的完整输出并传给 Cascade → **当前 XIAOMI_API_KEY 已暴露在 Cascade 对话上下文**。明天方案 A 搞完后，用户需到 token-plan 控制台轮换 key。今后类似场景应用 `sed -i 's/^XIAOMI_API_KEY=.*/XIAOMI_API_KEY=.../' $HERMES_HOME/.env`（IDE 不会抓内容），避免走 nano。

**待办**（按优先级）：
- [ ] **方案 A：搬 venv + 源码到 C 盘 ~/hermes-agent/**（rsync 代码 + 重装 413 包，15 分钟）
- [ ] 验证 MiMo 连通：`hermes` → 问一句话，看是否返回
- [ ] **轮换 XIAOMI_API_KEY**（安全修复）
- [ ] §2.5 关闭 `skills.auto_create` 和 `skills.auto_improve`
- [ ] §3 跑 6 步验收（**特别是写入边界测试：让 Hermes 试写 `~/shadowblade/test.txt` 应被拒**）
- [ ] §2.4 配 Telegram bot（可选，不急）
- [ ] 更新 `docs/hermes_setup.md`（.env 路径、XIAOMI_API_KEY 变量名、方案 A 性能节）
- [ ] 部署 §4 任务 A/B/C（爬 ClawHub 样本 / 每日竞品论文搜索 / 爬 GitHub skill 仓库）

**配置过程中要避坑**（比旧版多两条）：
- ❌ 绝不用 `run_command` 跑 `hermes` 交互向导 —— 会要 API key 输入，pipe 模式下可能再次回显
- ❌ 绝不用 `nano` 打开含敏感值的文件 —— IDE 会抓取完整输出传给 Cascade
- ❌ `hermes model` 向导一旦开始就别 Ctrl+C，让 15s timeout 自己触发 fallback
- ✅ 配置由用户在自己 WSL 终端跑 `hermes model` 或 `hermes config set ...`，Cascade 只指导命令
- ✅ 敏感值改用 `sed -i` 或 `printf | tee` 风格，让 IDE 看不到内容

---

### 2026-05-09 Hermes Agent 本体安装完成 ✅（归档）

**最终结果**：`hermes --version` 输出 `Hermes Agent v0.12.0 (2026.4.30) / Up to date`，已链接到 `~/.local/bin/hermes`。venv site-packages 装了 **413 个包**，uv 缓存 1.3 GB。

**关键学习**：
1. **绕过 install.sh 的 git pull 是对的** —— 直接用 `uv pip install -e ".[all]"` 装依赖，比走 install.sh 稳得多（GitHub 不稳定时不被卡）
2. **清华 PyPI 镜像加速效果显著** —— 5/9 重跑只用 11 分钟装完全部 413 包（包含编译），vs 5/7 晚 21 分钟还没装完
3. **uv 缓存幂等性可靠** —— 5/7 晚 Ctrl+C 留下的 268 MB 缓存被 5/9 重跑完全复用

---

### 2026-05-08 Hermes Agent 安装进度（已解决，归档）

**当时卡点**：`install.sh` 在「Updating existing installation」步骤 git pull 失败（`error: RPC failed; curl 56 Recv failure: Connection reset by peer`）—— **GitHub 国内抽风**，与镜像源/工具链无关。**5/9 通过绕过 install.sh、直接 `uv pip install` 解决**。

**已完成的安装步骤**（昨晚 + 今天，全部可复用）：
- ✅ `HERMES_HOME=/mnt/d/hermes_data/hermes_home` 已设置 + 持久化到 `~/.bashrc`
- ✅ `UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` 已设置 + 持久化到 `~/.bashrc`（清华 PyPI 镜像）
- ✅ `uv 0.11.11` 已装在 `~/.local/bin/uv`
- ✅ apt 包：`build-essential` / `libffi-dev` / `python3-dev` / `ripgrep 14.1.0` 全装好（昨晚 sudo 装的）
- ✅ 源码：`/mnt/d/hermes_data/hermes_home/hermes-agent/`（git clone 完整，262 MB）
- ✅ Python 3.11.15 venv：`/mnt/d/hermes_data/hermes_home/hermes-agent/venv/`（昨晚 install.sh 创建）
- ✅ uv 缓存：`~/.cache/uv/`（268 MB，昨晚下了一部分依赖，重跑会复用）
- ❌ Python 依赖未装完（venv site-packages 仅 2 个文件，应有 100+）
- ❌ `~/.local/bin/hermes` 命令链接未创建
- ❌ 配置（MiMo provider、Telegram、关闭 auto_create skill）全部待做

**关键安全事件**（已处理）：5/7 晚 install.sh 在 sudo 提示符回显了用户密码（curl|bash 经 pipe 喂 stdin 时 sudo 不切换 echo off），用户已在 WSL 跑 `passwd` 改新密码。**今后绝不通过 `run_command` 跑会要 sudo 的命令**。

**下次开工的具体命令**（绕过 install.sh 的 git pull，直接装依赖）：
```bash
# 1. 直接用 uv 装依赖到现有 venv（跳过 git pull）
uv pip install --python /mnt/d/hermes_data/hermes_home/hermes-agent/venv/bin/python -e "/mnt/d/hermes_data/hermes_home/hermes-agent[all]"

# 2. 创建 hermes 命令链接
mkdir -p ~/.local/bin
ln -sf /mnt/d/hermes_data/hermes_home/hermes-agent/venv/bin/hermes ~/.local/bin/hermes

# 3. 验证
hermes --version
```
预计 3-5 分钟（清华镜像 + 复用昨晚缓存）。

**手册位置**：`docs/hermes_setup.md` v2，§2.1-§3 章节。注意手册里的 install.sh 入口已修正为 `https://hermes-agent.nousresearch.com/install.sh`（之前误写 GitHub raw URL）。

**安装完成后的下一步**：§2.2 配 MiMo（要 `MIMO_API_KEY`）、§2.4 配 Telegram bot token、§2.5 关闭 auto_create_skill、§3 跑 6 步验收（特别是验证 Hermes 是否真不能写 `~/shadowblade/`）。

---

### 2026-05-07 工具链决议：引入 Hermes Agent 作为第三 AI（v2 收紧）
- **背景**：CC + MiMo 联网失败（根因：CC 的 `WebSearch` 是 Anthropic 服务端工具，跨 provider 不存在）
- **决议**：引入 Nous Research 的 Hermes Agent，定位**纯外部杂活工人**——只搜索/爬虫/报告，不替换 Cascade 与 CC
- **边界 v2（按用户最新要求收紧）**：
  - Hermes **对 `~/shadowblade/` 整个项目目录只读**（含 src/、tests/、config/、docs/、data/、sandbox/、根文件全部）
  - 工作区迁出项目，落在 `/mnt/d/hermes_workspace/`（D 盘 148G 可用）
  - C 盘只剩 78G，加了磁盘监控 cron + Hermes 工作区 50G 硬上限 + WSL2 vhdx 月度收缩流程
  - 想合入项目的产出由用户/Cascade **人工 cp**，Hermes 自己不 cp
- **产出**：
  - `docs/hermes_setup.md`（v2，10+ 节，含磁盘防护章节）
  - `sandbox/README.md`（明确 Hermes 不写 sandbox/）
  - `.gitignore` 已回滚（无需特殊 hermes 条目，因为 Hermes 不再写项目）
- **决议文档**：`/home/niezekai/.windsurf/plans/networking-and-hermes-1b422c.md`
- **状态**：待用户执行安装（`curl ... install.sh | bash`），手册中 §2 步骤已就绪

### M1 ✅ 已完成（2026-04-28）
- WSL2 环境 + Python .venv
- Semgrep 1.161.0 + Bandit 1.9.4 + pip-audit 2.10.0
- Docker 29.4.1
- Qwen3-4B-AWQ 模型下载 + vLLM 0.20.0 推理验证通过
- Claude Code + MiMo-V2.5-Pro（原 DeepSeek V4 Pro，已切换）

### M2 进行中
- [x] SKILL.md 解析器（`src/static_engine/skill_parser.py`）— 12 测试通过
- [x] 静态扫描器 Semgrep + Bandit（`src/static_engine/scanner.py`）— 5 测试通过
- [x] AI 研判引擎 LLM 语义分析（`src/ai_engine/llm_judge.py`）— 12 测试通过
- [x] SSD 四子任务 Prompt（`judge_skill_ssd()`）— 参考 SkillSieve 论文
- [x] RAG 知识库 ChromaDB + BGE-small（`src/ai_engine/rag_knowledge.py`）— 8 测试通过
- [x] 恶意样本数据集 10 个 + 正常样本 5 个（`data/malicious/`, `data/benign/`）— 15 集成测试通过
- [x] 云端 API 切换（`src/ai_engine/llm_client.py`）— 支持 vLLM/MiMo/DeepSeek 三者切换，12 测试通过
- [x] **静态审计主流水线**（`src/static_engine/pipeline.py`）— 串通 S1+S2+S3+AI 的端到端审计 ✨
- [ ] FastAPI 后端框架（`src/api/`）
- [x] 连接 GitHub 远程仓库（`ZeKaiNie/shadowblade` 私有）

### M3 进行中（静态引擎全链路）
- [x] 主流水线 `pipeline.audit_skill()` — 35 测试通过
- [x] **真实样本检出率 100%（10/10）、误报率 0%（0/5）** ✨ 远超论文目标
- [ ] S4 typosquatting 相似度检测
- [ ] S5 LLM Guard PI 载荷检测
- [ ] S6 权限清单验证（声明 vs 实际行为对比）

### 后续里程碑
- **M3(W6)**: 静态引擎 v1.0 全链路（S1-S6 独立运行）
- **M4(W8)**: 动态引擎 v1.0（Docker+mitmproxy+蜜罐）
- **M5(W10)**: ReAct Agent + pipeline vs agent 对比
- **M6(W12)**: Streamlit 仪表盘 + 批量审计
- **M7(W20)**: 论文初稿
- **M8(W32)**: 结题

## 测试状态：100 测试（95 passed + 5 skipped） ✅

| 测试文件 | 数量 | 状态 |
|---------|------|------|
| `tests/test_skill_parser.py` | 12 | ✅ |
| `tests/test_scanner.py` | 5 | ✅ |
| `tests/test_llm_judge.py` | 12 | ✅（含 vLLM 集成测试 + SSD 子任务测试） |
| `tests/test_llm_client.py` | 13 | ✅（云端 API 配置加载 + 请求构造 + MiMo 集成测试） |
| `tests/test_rag_knowledge.py` | 8 | ✅ |
| `tests/test_real_samples.py` | 15 | ✅（真实样本集成测试） |
| `tests/test_pipeline.py` | 35 | ✅（评分公式 + 端到端 + 检出率指标）✨ |

## 量化指标目标 vs 当前

| 指标 | 目标 | 当前（仅静态） | 状态 |
|------|------|--------------|------|
| SKILL.md 恶意检出率 | ≥ 90% | **100%（10/10）** | ✅ 远超 |
| 静态误报率 | ≤ 15% | **0%（0/5）** | ✅ 远超 |
| 联合检出率（含 LLM） | ≥ 92% | 待 M3 LLM 接入后测 | ⏳ |
| OWASP AST10 覆盖度 | ≥ 7/10 | 4/10（AST01/02/04/05） | 🔄 进行中 |
| 单技能审计耗时 | ≤ 5 分钟 | < 0.2 秒（仅静态） | ✅ |
| 单卡 4060 8GB 运行 | 稳定 | 已验证 | ✅ |

注：当前样本量较小（10+5），需扩充至 ≥50 样本验证泛化性
