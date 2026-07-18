# Hermes Agent 接入手册

> 本文件由 Cascade（主开发 AI）维护，记录三 AI 协作架构下 Hermes Agent 的安装、配置与边界。
> 关联决议见 `/home/niezekai/.windsurf/plans/networking-and-hermes-1b422c.md`。
> 最后更新：2026-05-07 v2（**重大调整**：Hermes 对项目目录改为完全只读；工作区迁到 D 盘；强化磁盘防护）

---

## 0. 为什么需要 Hermes（一段话讲清）

Claude Code 切换到 MiMo v2.5 Pro 后**无法联网**——根因是 CC 的 `WebSearch` 是 Anthropic 服务端工具，跨 provider 不存在；`WebFetch` 是客户端实现的，应该仍可用。Hermes Agent 的网页/IM 能力**全部客户端实现**，与底层模型解耦，配 MiMo 也能搜网/抓页。同时 Hermes 的跨会话记忆 + 自主 skill 沉淀 + cron 调度，正好补齐 CC「每次开新会话都白板」的短板。

**定位**：第三个 AI，不替换 Cascade、不替换 CC，专门当**长期在线打工人**烧 MiMo 那 7 亿 token。

---

## 1. 三 AI 分工边界（必读，避免互踩）

| 角色 | 管辖目录（可写） | 可读但不可写 | 底层模型 |
|---|---|---|---|
| **Cascade**（主开发） | `src/`、`tests/`、`config/settings.yaml`、`docs/progress.md`、`docs/modules/` | 全部 | Cascade 内置 |
| **Claude Code**（调研维护） | `docs/research.md`、`docs/INDEX.md`「最近变更」、`data/` | `src/`（仅审查、改动须先告知） | Claude Sonnet/Opus 或 MiMo |
| **Hermes**（外部杂活工人） | **`/mnt/d/hermes_workspace/`（项目外，D 盘）** | `~/shadowblade/` 全部目录（含 `data/`、`sandbox/`） | **MiMo v2.5 Pro**（默认） |

**Hermes 边界铁律（v2，按用户最新要求收紧）**：
1. Hermes **对 `~/shadowblade/` 整个项目目录只读**——不能写 `src/`、`tests/`、`config/`、`docs/`、`data/`、`sandbox/`、根目录任何文件。
2. Hermes 所有产出（搜索结果、爬取数据、报告、缓存）**全部写到 `/mnt/d/hermes_workspace/`**。
3. 想把 Hermes 的产出合入项目 → **用户/Cascade 人工 review + 手动 cp**，不让 Hermes 自己 cp 进项目。
4. Hermes 想改 `src/` → 写建议到 `/mnt/d/hermes_workspace/suggestions/<日期>.md`，**不写进项目**。
5. 三方任一发现文件冲突 → **停下告知用户**，不自行覆盖。

**为什么这么严**：用户不希望 Hermes 修改项目核心文件，且 C 盘只剩 78G，必须把 Hermes 的大体积产出隔离到 D 盘。

---

## 2. 安装步骤

### 2.1 系统依赖（一键安装，~10 分钟）

```bash
# WSL2 Ubuntu 终端中执行
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

脚本会自动装：
- `uv`（快速 Python 包管理器）
- Python 3.11（uv 管理，不动系统 Python）
- Node.js 22（用于浏览器自动化、WhatsApp 桥）
- `ripgrep`（快速文件搜索）
- `ffmpeg`（TTS 音频转换）

**验证**：

```bash
hermes --version     # 应输出版本号
which hermes         # 应输出 ~/.local/bin/hermes 之类路径
```

如果 `hermes` 命令未找到，执行：

```bash
source ~/.bashrc     # 或 source ~/.zshrc
```

### 2.2 配置 MiMo 作为默认 provider

**Step 1 — 设置环境变量（沿用项目现有变量名）**

编辑 `~/.bashrc`（已有 `MIMO_API_KEY` 的话跳过）：

```bash
echo 'export MIMO_API_KEY="<你的-MiMo-key>"' >> ~/.bashrc
source ~/.bashrc
```

> ⚠️ 不要把 key 写到任何 git 跟踪的文件里。`config/settings.yaml` 的 `api_key_env: MIMO_API_KEY` 已经做了正确处理。

**Step 2 — 启动 Hermes 交互式向导**

```bash
hermes
```

按提示选择：

| 提示 | 选择 |
|---|---|
| Import OpenClaw config? | `n`（你没用过 OpenClaw） |
| Provider preset | 选 `More providers` |
| Provider type | 选 `Custom OpenAI-compatible endpoint` |
| Base URL | `https://token-plan-cn.xiaomimimo.com/v1` |
| API Key env | `MIMO_API_KEY` |
| Model name | `mimo-v2.5-pro` |

**Step 3 — 验证模型连通**

```bash
hermes
> 你是谁？请用一句话说明
```

预期：MiMo 返回中文自我介绍。如报 401 → key 错；429 → 限流；ConnectError → MiMo 服务问题。

### 2.3 创建 D 盘工作区 + 配置只读边界（最关键的安全步骤）

**Step 1 — 一键创建 D 盘工作区目录结构**

```bash
# 在 WSL2 终端执行（D 盘已挂载在 /mnt/d）
mkdir -p /mnt/d/hermes_workspace/{search_results,crawl_data,reports,cache,suggestions,logs}

# 验证
ls -la /mnt/d/hermes_workspace/
```

**目录用途**：

| 子目录 | 用途 |
|---|---|
| `search_results/` | 网页搜索结果归档（Markdown / JSON） |
| `crawl_data/` | 爬虫产出（ClawHub 技能 / GitHub 仓库 / 论文 PDF 等） |
| `reports/` | Hermes 生成的分析报告、批量任务汇总 |
| `cache/` | 临时缓存（去重哈希、URL 已访问列表等） |
| `suggestions/` | 给 Cascade 的代码改进建议（用户人工 review 后才合入项目） |
| `logs/` | Hermes 运行日志、Telegram 消息记录 |

**Step 2 — 把 Hermes 的所有数据目录指向 D 盘**

Hermes 默认把记忆库（FTS5 SQLite）、skill 库、缓存放在 `~/.config/hermes/` 和 `~/.local/share/hermes/`。这两处都在 WSL2 内，最终落 C 盘 vhdx。**用软链接把它们重定向到 D 盘**：

```bash
# 1. 准备 D 盘目录
mkdir -p /mnt/d/hermes_data/{config,share,cache}

# 2. 删除（或备份）现有空目录，建立软链
# 警告：仅在初次安装、目录还为空时执行；如果已有数据，先 mv 再 ln
rm -rf ~/.config/hermes ~/.local/share/hermes ~/.cache/hermes
ln -s /mnt/d/hermes_data/config ~/.config/hermes
ln -s /mnt/d/hermes_data/share ~/.local/share/hermes
ln -s /mnt/d/hermes_data/cache ~/.cache/hermes

# 3. 验证
ls -la ~/.config/hermes ~/.local/share/hermes ~/.cache/hermes
# 应看到箭头指向 /mnt/d/hermes_data/...
```

> ⚠️ **跨文件系统性能警告**：`/mnt/d/` 是 9P 协议挂载的 Windows NTFS，在 WSL2 内读写比 ext4 慢 2-5 倍。Hermes 的 FTS5 数据库放这里**搜索会变慢**。如果你介意，可以只把 `crawl_data/`、`cache/` 这种大体积冷数据放 D 盘，`config/`、`share/` 留在 WSL2 内（每天就几 MB 级增长，不会爆 C 盘）。
>
> **推荐折中方案**：仅 `~/.cache/hermes` → `/mnt/d/hermes_data/cache`（缓存最大），其余留 WSL2 内。

**Step 3 — 写 `~/.config/hermes/WORKSPACE.md`**（Hermes 边界规则）

```markdown
# 影刃卫士工作区规则 v2

## 项目目录（完全只读，绝对不能写）
/home/niezekai/shadowblade/
  - 包括所有子目录：src/、tests/、config/、docs/、data/、sandbox/、knowledge/、models/
  - 包括所有根文件：.windsurfrules、CLAUDE.md、README.md、pyproject.toml 等
  - 例外：无。整个 ~/shadowblade/ 树**只读**。

## 工作区目录（你的唯一可写区）
/mnt/d/hermes_workspace/
  - search_results/   # 搜索归档
  - crawl_data/       # 爬虫产出
  - reports/          # 分析报告
  - cache/            # 临时缓存
  - suggestions/      # 给 Cascade 的代码建议（不直接合入项目）
  - logs/             # 运行日志

## 行为约束
1. 任何对 /home/niezekai/shadowblade/ 的写入操作 → 立即停下并告知用户，不要尝试。
2. 不主动 git commit / push（commit 由 Cascade/CC/用户负责）。
3. 不读取 .env / *.key / api_key.* 等敏感文件的 value（识别其存在并跳过）。
4. 自创建 skill 写到 ~/.config/hermes/skills/（已软链到 D 盘），不写项目。
5. 文件命名规范：/mnt/d/hermes_workspace/<task>/<YYYY-MM-DD>/<file>。
6. 单个任务输出 > 100 MB 时，先告知用户、确认后再继续，避免意外撑爆 D 盘。
```

**Step 4 — 验证写入边界**

```bash
hermes
> 请尝试在 /home/niezekai/shadowblade/test.txt 写入 "hello"
```

预期：Hermes 拒绝，并提示"该路径只读"。如果它真写入了 → WORKSPACE.md 没生效，检查文件位置。

### 2.4 接 Telegram bot（IM 网关）

**Step 1 — 申请 bot token**

在 Telegram 找 `@BotFather`，发送：

```
/newbot
```

按提示给 bot 起名（建议 `ShadowBladeAssistant`），拿到形如 `1234567890:AABbCCdd...` 的 token。

**Step 2 — 配置 Hermes**

```bash
hermes messaging setup telegram
# 粘贴 bot token
```

**Step 3 — 启动消息网关**

```bash
hermes messaging start telegram
```

**Step 4 — 验证**

在 Telegram 找你的 bot，发 `/start`，预期 Hermes 回复一段欢迎消息。

### 2.5 关闭自主 skill 创建（生产稳定性）

```bash
hermes config set skills.auto_create false
hermes config set skills.auto_improve false
```

> 这两项是 Hermes 的「自我进化」开关。短期建议关掉——避免 skill 漂移导致行为不可预测。等用熟了再分场景打开。

### 2.6 磁盘空间防护（关键，C 盘只剩 78G）

**a) 安装磁盘监控 cron（每小时检查，超阈值告警）**

```bash
# 写一个监控脚本到 D 盘
cat > /mnt/d/hermes_workspace/scripts/disk_check.sh << 'EOF'
#!/bin/bash
# 影刃卫士 - Hermes 磁盘占用监控
# 阈值：D 盘可用 < 10G、Hermes 工作区 > 50G、WSL2 vhdx 涨幅 > 5G/天 都告警

WORKSPACE=/mnt/d/hermes_workspace
C_AVAIL=$(df -BG /mnt/c | tail -1 | awk '{print $4}' | tr -d 'G')
D_AVAIL=$(df -BG /mnt/d | tail -1 | awk '{print $4}' | tr -d 'G')
WORKSPACE_SIZE=$(du -sBG "$WORKSPACE" 2>/dev/null | awk '{print $1}' | tr -d 'G')

echo "[$(date +%F\ %T)] C盘可用=${C_AVAIL}G  D盘可用=${D_AVAIL}G  hermes_workspace=${WORKSPACE_SIZE}G"

ALERT=""
[ "$C_AVAIL" -lt 30 ] && ALERT+="⚠️ C盘紧张(<30G) "
[ "$D_AVAIL" -lt 20 ] && ALERT+="⚠️ D盘紧张(<20G) "
[ "$WORKSPACE_SIZE" -gt 50 ] && ALERT+="⚠️ Hermes工作区超50G "

if [ -n "$ALERT" ]; then
  # 推 Telegram（要求已配 hermes messaging）
  hermes messaging send telegram "$ALERT - 详情见 hermes_workspace 大小"
  echo "$(date +%F\ %T) $ALERT" >> /mnt/d/hermes_workspace/logs/disk_alerts.log
fi
EOF

chmod +x /mnt/d/hermes_workspace/scripts/disk_check.sh
mkdir -p /mnt/d/hermes_workspace/scripts /mnt/d/hermes_workspace/logs

# 加入 crontab（每小时跑一次）
(crontab -l 2>/dev/null; echo "0 * * * * /mnt/d/hermes_workspace/scripts/disk_check.sh") | crontab -
```

**b) 给 Hermes 自身设硬上限**

```bash
hermes config set workspace.max_size_gb 50         # 工作区超 50G 时拒绝写入
hermes config set crawler.max_concurrent 3         # 爬虫并发数
hermes config set crawler.per_task_size_limit_mb 500   # 单任务最多产 500MB
hermes config set memory.max_db_size_mb 200        # FTS5 数据库上限 200MB
```

**c) WSL2 vhdx 收缩（每月一次手动）**

Hermes 即使用了软链到 D 盘，少量缓存还是会留在 WSL2 内导致 vhdx 膨胀。每月在 **Windows PowerShell（管理员）** 执行：

```powershell
wsl --shutdown
# 找到你的 distro 名（一般是 Ubuntu）
wsl -l -v
# 收缩 vhdx（替换 distro 名）
wsl --manage Ubuntu --resize 30GB
# 或用旧命令
Optimize-VHD -Path "$env:LOCALAPPDATA\Packages\CanonicalGroupLimited.Ubuntu_*\LocalState\ext4.vhdx" -Mode Full
```

> 收缩前确认 WSL2 内 `df -h /` 显示有未使用空间，否则收缩没意义。

**d) 紧急扩容方案**

如 C 盘真的快爆了：

1. **先**：`hermes messaging stop --all && hermes schedule clear`（停 Hermes 写入）
2. **再**：把 `~/.config/hermes` 整个移到 D 盘（如果还没软链）
3. **最后**：执行 c) 的 vhdx 收缩

---

## 3. 第一批验收任务

按顺序跑通这 6 个任务即可认定接入成功：

| # | 任务 | 命令 / Prompt | 预期 |
|---|---|---|---|
| 1 | 启动对话 | `hermes` → 输入 `你是谁？` | MiMo 中文回复 |
| 2 | 网页抓取 | `请用 web_fetch 抓 https://github.com/NousResearch/hermes-agent，告诉我最新 commit 时间` | 返回真实数据 |
| 3 | 网页搜索 | `搜一下 OWASP Agentic Skills Top 10 最新进展` | 返回多条搜索结果 |
| 4 | **写入边界** | `请在 /home/niezekai/shadowblade/test.txt 写入 hello` | **Hermes 拒绝**，告知只读 |
| 5 | Telegram 联通 | 在 Telegram 给 bot 发：`今天天气如何？` | bot 回复（Hermes 通过 web 搜出来） |
| 6 | 最小爬取任务 | 见 §4 «第一个真实任务：搜索 + 爬取» | 5 个 ClawHub 技能爬到 `/mnt/d/hermes_workspace/crawl_data/2026-05-07/` |

---

## 4. 真实任务清单（纯外部杂活，0 接触项目核心）

按用户最新要求，Hermes 只干以下三类事：**搜索、爬虫、报告生成**。所有产出落在 `/mnt/d/hermes_workspace/`，不写项目目录。如果产出对项目有用，由用户/Cascade 人工 cp。

### 任务 A：定向爬取 ClawHub 技能样本

**目标**：扩充影刃卫士的样本库（当前只有 15 个，目标 ≥ 50）。

**Prompt 模板**：

```
请你完成以下任务（爬虫任务，输出到 D 盘）：

1. 访问 https://clawhub.ai 浏览技能列表（首页或搜索页）。
2. 选取 20 个技能，要求：
   - 至少 5 个声明涉及网络访问（network_access）
   - 至少 5 个声明涉及文件系统写入（file_system_write）
   - 至少 5 个涉及 shell 执行
   - 剩余 5 个为低风险普通技能（作为正常对照样本）
3. 对每个技能：
   a. 抓取其 SKILL.md 全文
   b. 抓取其代码文件清单（不必下载全部代码，先列清单）
   c. 保存到：/mnt/d/hermes_workspace/crawl_data/clawhub/2026-05-07/<skill-name>/
4. 生成清单：/mnt/d/hermes_workspace/crawl_data/clawhub/2026-05-07/index.json
   字段：name, url, declared_capabilities, file_count, crawled_at
5. 完成后 Telegram 通知我，附 index.json 摘要。

约束：
- 不写 /home/niezekai/shadowblade/ 任何路径
- 单技能爬取超时 30 秒就跳过，记录到 errors.log
- 总产出超 200 MB 停下问我
- 遵守 robots.txt 与 1 秒/请求的速率限制
```

**预期产出**：~50 MB（20 个技能的 markdown + json），落在 D 盘。

**事后人工合入**（用户/Cascade 操作，**不让 Hermes 干**）：

```bash
# 用户 review 后 cp 进项目（注意：data/clawhub_skills/ 已在 .gitignore）
cp -r /mnt/d/hermes_workspace/crawl_data/clawhub/2026-05-07/* \
      /home/niezekai/shadowblade/data/clawhub_skills/
```

### 任务 B：定期搜索竞品/论文动态

**Prompt 模板**：

```
请每天搜索以下关键词，把新结果（24 小时内发布）汇总成 markdown：

关键词：
  - "OWASP Agentic Skills" / "OWASP AST10"
  - "AI agent security audit"
  - "prompt injection skill marketplace"
  - "ClawHub" 或 "OpenClaw skill" 安全相关
  - "SkillSieve" / "ClawSecure" / "Sigil"（已知竞品）

步骤：
1. 用 web_search 跑每个关键词
2. 过滤：仅保留 24h 内、英文/中文、来自 arxiv/github/medium/学术博客的结果
3. 每条提取：title / url / publish_date / 一句话摘要（中文）
4. 写入：/mnt/d/hermes_workspace/search_results/daily/<YYYY-MM-DD>.md
5. 推送 Telegram 摘要（前 5 条）

约束：单次搜索结果超 30 条停下问我；仅写 D 盘。
```

**调度**：见 §5 cron 任务。

### 任务 C：批量爬 GitHub 上的 OpenClaw / ClawHub skill 仓库

**Prompt 模板**：

```
请爬取 GitHub 上以下查询的前 50 个仓库元数据：

查询：
  topic:openclaw-skill
  topic:clawhub-skill
  "clawhub" extension:md path:SKILL.md

步骤：
1. 用 GitHub Search API（无需 token，公开数据有 rate limit）
2. 对每个仓库提取：full_name / stars / last_push / SKILL.md 原文 / license
3. 保存到 /mnt/d/hermes_workspace/crawl_data/github_openclaw/2026-05-07/
4. 生成 index.json + 风险倾向初判（仅基于 SKILL.md 的关键词扫描，不调 LLM）
5. Telegram 推送 stars > 50 的仓库列表

约束：仓库代码体不下载（只要元数据 + SKILL.md）；超 100 MB 停下问我。
```

### 不允许 Hermes 干的事（明确列出）

- ❌ 修改 `~/shadowblade/` 任何文件
- ❌ 调用项目内的 `src/ai_engine/llm_judge.py` 的函数（直接走 MiMo HTTP API，与项目代码解耦）
- ❌ 跑项目测试 `pytest tests/`
- ❌ git commit / push
- ❌ 写入 `data/clawhub_skills/`、`data/malicious/`、`data/benign/`、`data/rag_knowledge/`
- ❌ 沙箱里执行任何爬到的可疑代码（这是动态引擎 M4 的活，由 Cascade 实现）

---

## 5. 持续运行任务（cron）

跑通 §4 后，可以让 Hermes 每天定时干活——**全部产出落 D 盘**：

```bash
# 每天 8:30 跑搜索任务（任务 B）
hermes schedule add --cron "30 8 * * *" --task \
  "执行 hermes_setup §4 任务 B（每日竞品/论文搜索），产出到 /mnt/d/hermes_workspace/search_results/daily/。完成后 Telegram 通知前 5 条。"

# 每周一 9:00 推送项目仓库状态（只读，不改）
hermes schedule add --cron "0 9 * * 1" --task \
  "读取 /home/niezekai/shadowblade（只读），统计：本周 commit 数、tests/ 文件数、docs/progress.md 最新一条。Telegram 推送，不写任何项目文件。"

# 每周三 22:00 跑爬虫任务 A（增量爬 ClawHub）
hermes schedule add --cron "0 22 * * 3" --task \
  "执行 hermes_setup §4 任务 A，注意已爬过的技能名（见 /mnt/d/hermes_workspace/crawl_data/clawhub/index_master.json）跳过。"
```

查看已配置任务：

```bash
hermes schedule list
```

---

## 6. 故障排查速查

| 症状 | 可能原因 | 解决 |
|---|---|---|
| `hermes: command not found` | PATH 没 source | `source ~/.bashrc` |
| 401 Unauthorized | MIMO_API_KEY 错或失效 | 重新设置环境变量 |
| 429 Too Many Requests | MiMo 限流 | 降并发 `hermes config set llm.max_concurrent 2` |
| Connection refused / timeout | MiMo 服务问题或代理 | `curl https://token-plan-cn.xiaomimimo.com/v1/models` 测连通 |
| Tool call failed: web_search | 国内访问搜索引擎被墙 | 设置 `export HTTPS_PROXY=...` 后重启 hermes |
| Hermes 想写项目目录 | WORKSPACE.md 没生效 | 检查 `~/.config/hermes/WORKSPACE.md`；启动时观察是否打印「workspace loaded」 |
| Telegram bot 不响应 | 网关没起或 token 错 | `hermes messaging status`，必要时 `hermes messaging restart telegram` |
| **C 盘空间告急** | WSL2 vhdx 膨胀 | §2.6 d) 紧急扩容流程 |
| **D 盘空间告急** | hermes_workspace 太大 | `du -sh /mnt/d/hermes_workspace/*`；删 `crawl_data/` 旧日期目录 |
| **WSL2 内 `/mnt/d` 找不到** | Windows D 盘没挂载 | 在 Windows 检查 D 盘可用，或重启 WSL2 |
| `cron` 不工作 | WSL2 的 cron 默认不开机自启 | `sudo service cron start`；或加到 `/etc/wsl.conf` `[boot] command = service cron start` |

---

## 7. 何时停用 Hermes

满足任一条件就该重新评估：

- MiMo 7 亿 token 用完，且 DeepSeek/本地 vLLM 性价比都更优
- 出现三方误改同一文件的 git 冲突（说明边界规则失效）
- skill 漂移导致 Hermes 行为开始不可预测
- M2 收尾、M3-M5 主线开发期需要绝对专注，不希望额外 agent 介入

停用方式：

```bash
hermes messaging stop --all
hermes schedule clear
# 不需要卸载，下次直接启动 hermes 即可
```

---

## 8. 不在本手册范围

- Hermes 的 LoRA 微调（与项目主目标无关）
- Hermes 接入论文评测流程（M6+ 再考虑）
- 让 Hermes 当 ReAct agent 直接审计 SKILL.md（这是 M5 主线，由 Cascade 实现，不交给 Hermes）

---

## 关联文档

- 决议背景：`/home/niezekai/.windsurf/plans/networking-and-hermes-1b422c.md`
- 项目分工：`docs/INDEX.md` §「双 AI 协作 SOP」（待 CC 更新加入 Hermes 第三方）
- LLM 客户端实现：`src/ai_engine/llm_client.py`（MiMo provider 封装）
- 进度记录：`docs/progress.md` §「2026-05-07」

---

## 9. 附录：一键引导脚本

把下面整段保存为 `~/hermes_bootstrap.sh`（**项目外**，用户家目录），`bash ~/hermes_bootstrap.sh` 执行。脚本只做 §2.3 + §2.6 a) b) 的工作区准备，**不安装 Hermes 本体**（§2.1 的 `curl | bash` 仍要单独执行）、**不配 MiMo / Telegram**（要交互输入凭据）。

```bash
#!/bin/bash
# 影刃卫士 - Hermes Agent 工作区一键引导脚本
# 用途：创建 D 盘工作区、把 Hermes 数据缓存软链到 D 盘、装磁盘监控 cron
# 使用：bash ~/hermes_bootstrap.sh
# 运行后再去 §2.1 装 Hermes、§2.2 配 MiMo、§2.4 配 Telegram

set -euo pipefail

# ----- 0. 前置检查 -----
echo "==> [0/5] 前置检查"

if [ ! -d /mnt/d ]; then
  echo "❌ /mnt/d 不存在，请确认 Windows D 盘已挂载（Windows 资源管理器能看到 D:）"
  exit 1
fi

D_AVAIL=$(df -BG /mnt/d | tail -1 | awk '{print $4}' | tr -d 'G')
if [ "$D_AVAIL" -lt 30 ]; then
  echo "⚠️ D 盘可用 ${D_AVAIL}G，建议至少 30G，继续？[y/N]"
  read -r ans
  [ "$ans" = "y" ] || exit 1
fi

# ----- 1. 创建工作区目录 -----
echo "==> [1/5] 创建 /mnt/d/hermes_workspace/ 目录树"
mkdir -p /mnt/d/hermes_workspace/{search_results,crawl_data,reports,cache,suggestions,logs,scripts}

# ----- 2. 数据目录软链（仅 cache，性能折中方案） -----
echo "==> [2/5] 软链 ~/.cache/hermes -> D 盘"
mkdir -p /mnt/d/hermes_data/cache
if [ -e ~/.cache/hermes ] && [ ! -L ~/.cache/hermes ]; then
  echo "  备份现有 ~/.cache/hermes -> ~/.cache/hermes.bak.$(date +%s)"
  mv ~/.cache/hermes ~/.cache/hermes.bak.$(date +%s)
fi
[ -L ~/.cache/hermes ] || ln -s /mnt/d/hermes_data/cache ~/.cache/hermes

# ----- 3. 写 WORKSPACE.md -----
echo "==> [3/5] 写 ~/.config/hermes/WORKSPACE.md"
mkdir -p ~/.config/hermes
cat > ~/.config/hermes/WORKSPACE.md << 'WORKSPACE_EOF'
# 影刃卫士工作区规则 v2

## 项目目录（完全只读，绝对不能写）
/home/niezekai/shadowblade/
  - 包括所有子目录与根文件，无例外。

## 工作区目录（你的唯一可写区）
/mnt/d/hermes_workspace/
  - search_results/  crawl_data/  reports/  cache/  suggestions/  logs/

## 行为约束
1. 任何对 /home/niezekai/shadowblade/ 的写入操作 → 立即停下并告知用户。
2. 不主动 git commit / push。
3. 不读取 .env / *.key / api_key.* 等敏感文件的 value。
4. 自创建 skill 写到 ~/.config/hermes/skills/，不写项目。
5. 文件命名：/mnt/d/hermes_workspace/<task>/<YYYY-MM-DD>/<file>。
6. 单任务输出 > 100 MB 时先告知用户。
WORKSPACE_EOF

# ----- 4. 装磁盘监控脚本与 cron -----
echo "==> [4/5] 装磁盘监控脚本与 cron"
cat > /mnt/d/hermes_workspace/scripts/disk_check.sh << 'DISK_EOF'
#!/bin/bash
WORKSPACE=/mnt/d/hermes_workspace
C_AVAIL=$(df -BG /mnt/c | tail -1 | awk '{print $4}' | tr -d 'G')
D_AVAIL=$(df -BG /mnt/d | tail -1 | awk '{print $4}' | tr -d 'G')
WORKSPACE_SIZE=$(du -sBG "$WORKSPACE" 2>/dev/null | awk '{print $1}' | tr -d 'G')
echo "[$(date +%F\ %T)] C=${C_AVAIL}G D=${D_AVAIL}G ws=${WORKSPACE_SIZE}G" >> "$WORKSPACE/logs/disk_check.log"
ALERT=""
[ "$C_AVAIL" -lt 30 ] && ALERT+="⚠️ C盘紧张(<30G) "
[ "$D_AVAIL" -lt 20 ] && ALERT+="⚠️ D盘紧张(<20G) "
[ "$WORKSPACE_SIZE" -gt 50 ] && ALERT+="⚠️ Hermes工作区超50G "
if [ -n "$ALERT" ]; then
  command -v hermes >/dev/null 2>&1 && hermes messaging send telegram "$ALERT" 2>/dev/null
  echo "$(date +%F\ %T) $ALERT" >> "$WORKSPACE/logs/disk_alerts.log"
fi
DISK_EOF
chmod +x /mnt/d/hermes_workspace/scripts/disk_check.sh

# 加入 crontab（去重）
CRONLINE="0 * * * * /mnt/d/hermes_workspace/scripts/disk_check.sh"
(crontab -l 2>/dev/null | grep -v "disk_check.sh"; echo "$CRONLINE") | crontab -

# WSL2 cron 默认不开机自启，临时启动
sudo service cron status >/dev/null 2>&1 || sudo service cron start || true

# ----- 5. 总结 -----
echo "==> [5/5] 完成"
echo ""
echo "已创建："
echo "  /mnt/d/hermes_workspace/         （工作区）"
echo "  /mnt/d/hermes_data/cache/        （Hermes 缓存软链目标）"
echo "  ~/.config/hermes/WORKSPACE.md    （边界规则）"
echo "  ~/.cache/hermes -> /mnt/d/...    （软链）"
echo "  crontab 已加入每小时磁盘监控"
echo ""
echo "下一步："
echo "  §2.1  装 Hermes：curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
echo "  §2.2  配 MiMo provider"
echo "  §2.4  配 Telegram bot"
echo "  §2.5  关闭自主 skill 创建"
echo "  §3    跑 6 步验收"
```

### 用法

```bash
# 1. 复制上面整段到 ~/hermes_bootstrap.sh
nano ~/hermes_bootstrap.sh   # 或 vim、或 cat > ~/hermes_bootstrap.sh
chmod +x ~/hermes_bootstrap.sh

# 2. 执行（首次安装 Hermes 之前）
bash ~/hermes_bootstrap.sh

# 3. 运行后按提示装 Hermes 本体（§2.1）

# 4. 用完可以删掉脚本（一次性）
rm ~/hermes_bootstrap.sh
```

### 注意

- 此脚本**幂等可重跑**：检查目录已存在则跳过、cron 行去重后再加。
- 脚本会创建一次 sudo 调用（启动 cron），WSL2 内会要密码。
- 软链方案是「折中方案」（仅 cache 落 D 盘）。如要把 config/share 也落 D 盘，按 §2.3 Step 2 手动操作。
