# 开发进度

> 最后更新：2026-07-18（方向 A 小批实验跑通：真实样本上得到高精度/零误报/低召回的第一手数据）

---

## ⭐ 当前主线（新开会话从这里接续）

- **研究方向锁定 A+B**（同一套 per-run 蜜罐/canary 污点方法打两个面）：
  - **A（保底·有公开数据 MalSkillBench）**：运行时接地能力一致性核验 + 蜜罐取证 + 阻断，专打 prompt-injection / agent 控制面（B10–B15）。
  - **B（新颖·需自建）**：跨 App 共享上下文投毒的检测/防御/基准（ChatGPT Apps）。**B 不阻塞 A**。
- **已完成**：数据加载器 + 评测框架 + baseline 复现 + 声明能力抽取/`allowed-tools` + 一致性核验 + 决策 + 动态沙箱（含依赖兜底 shim）+ 端到端管线。
- **真实第一手结果**（50 恶意/50 良性含脚本子集，隔离 Docker）：**P=1.00 / FPR=0.00 / Recall=0.16 / F1=0.28 / 蜜罐命中=0**，即**高精度零误报低召回确认层**（见 `docs/planning/小批实验结果_方向A.md`）。
- **诱饵扩展（v2）已做**：蜜罐诱饵扩到 ~20 个（钱包/助记词/浏览器/云凭据）+ "读凭据即 credential_access" 信号 + IOC 扩充。**同 50/50 重跑 = 与 v1 完全一致（R 仍 0.16、蜜罐 0）**。逐样本核查发现**真正瓶颈是执行触发**：50 恶意样本运行时 0 个读到诱饵/命中蜜罐，因恶意逻辑多藏在未被调用的函数里（顶层直跑触发不到，见 `docs/planning/小批实验结果_方向A.md` 第 5 节）。诱饵机制本身已用合成样本验证正确。
- **下一步（待用户确认）**：① **入口触发**（顶层跑完自动调用 `main()`/定义的函数，仍在 Docker 隔离内）——这才是提召回的关键；② 可疑目标信誉 + 下载-执行链规则；③ 重跑更大批；④ 消融 + 跨数据集泛化；⑤ 方向 B 测试台；⑥ 论文初稿 + arXiv preprint。
- **PR 现状**：#4/#5/#6/#7 均已合入 main。
- **协作**：Devin push GitHub 遇 403，改由用户在 antigravity `git am` 补丁开 PR；恶意样本只在 Docker 隔离执行。

> ⚠️ 本文件下方「M2/M3、Hermes、MiMo key、M4-M8 里程碑、检出率 100%(10/10)」等属**历史存档，已不代表当前路线**，仅留作记录，勿作为接续指引。当前主线以本节 + `docs/planning/` 为准。

---

### 2026-07-18 — 方向 A：诱饵扩展 v2 + 凭据读取信号（Devin）

- ✅ **蜜罐诱饵扩展**（`dynamic_engine/honeypot.py`）：4→~20 个诱饵，覆盖加密钱包/助记词
  (`wallet_seed.txt`/`.electrum`/`.ethereum/keystore`/Exodus/`wallet.dat`/MetaMask 扩展存储)、
  浏览器登录数据/Cookie、云与开发者凭据(`.aws/credentials`/gcloud/`.git-credentials`/`.npmrc`/`.docker`/`.kube`)；
  内容按格式仿真并各自嵌唯一 marker。IOC 扩充 discord CDN/telegram/rentry/gofile 等。
- ✅ **"读凭据即 credential_access"**：`monitor` 记录读取到的敏感/诱饵路径 `credential_read_paths`，
  `capabilities.observed_from_audit` 据此加 `credential_access`（敏感能力）→ 未声明即至少 review；正常技能不读，故 FPR 不受损。
- ✅ **同 50/50 重跑（`runs/pilot50_v2.json`）= 与 v1 完全一致**（P=1.00/R=0.16/F1=0.28/FPR=0.00/蜜罐=0）。
  诚实归因：50 恶意样本运行时 **0 个读到诱饵/命中蜜罐**——瓶颈是**执行触发**（恶意逻辑藏在未调用函数里，
  顶层直跑触发不到），不是诱饵覆盖。机制本身已用合成样本验证正确（读 AWS 凭据→review、钱包外传→deny）。
- ✅ 测试：新增诱饵覆盖/凭据读取映射单测；改动文件 ruff 干净，动态+一致性相关 41 passed。
- ⏭️ 待确认的关键下一步：**受控入口触发**（Docker 隔离内自动调用 `main()`/定义的入口），预期显著提升执行到率与召回。

### 2026-07-18 — 方向 A：动态引擎依赖兜底 + allowed-tools 声明 + 真实样本小批实验（Devin）

- ✅ **依赖兜底 shim**（`src/dynamic_engine/sandbox_shims/`）：让缺第三方库(requests 等)的技能代码
  也能在最小镜像里跑到暴露行为那一步。联网类库(requests/httpx/wget/urllib3)用真 urllib 实现，
  联网/外传动作可被审计并命中蜜罐；其它缺失库用宽容占位(_autostub)顶上。
- ✅ **harness 修复**：过滤解释器/库/shim 的 import 噪声与文件描述符伪写；修正 `_is_write_mode`
  只看 mode/flags（此前路径含 'w' 会被误判为写）。
- ✅ **allowed-tools 声明解析**（`conformance/capabilities.parse_allowed_tools`）：把 Agent Skills 的
  `allowed-tools: Read, WebFetch, Bash(...)` 映射为声明能力，声明侧更贴近真实授权。
- ✅ **小批实验脚本** `scripts/run_pilot_batch.py`：真实 MalSkillBench 50 恶意 + 50 良性(含脚本子集)，
  隔离 Docker 执行 → 一致性核验 → 决策 → P/R/F1/FPR。
- ✅ **第一手真实结果**：Precision=1.00, FPR=0.00, Recall=0.16, F1=0.28, 蜜罐命中=0；良性 0 误报。
  详见 `docs/planning/小批实验结果_方向A.md`（含诚实归因与下一步：诱饵扩展/可疑目标信誉/下载-执行链）。
- ✅ 测试：新增 shim/allowed-tools 单测；全套 126 passed + 10 skipped。

## 🗄️ 历史存档（以下为旧路线，已作废，勿作接续指引）

> 下面所有内容（Hermes/MiMo key 轮换、"新会话接续指南 M3 选项 B"、M2-M8 里程碑、
> "检出率 100%(10/10)/误报 0%(0/5)"等）均为**方向修正前的旧路线与编造/小样本指标**，
> 仅留作历史记录。**当前主线以本文件顶部「⭐ 当前主线」+ `docs/planning/` 为准。**

> 最后更新（历史）：2026-07-18（**Hermes 已完全弃用与清理**，焦点回归 M3 静态引擎与 M4 动态沙箱）

## 当前状态：M2 → M3 过渡（静态全链路打通）+ M4 动态引擎最小闭环已落地

### 2026-07-18 — 项目整理 + 主页/文档校正（Devin）

- ✅ 更新 `README.md`：加"开发状态"进度表、核心原理、运行测试与用法示例、安全提示
- ✅ 移除个人知识库 `knowledge/`（Obsidian 私人笔记 + 两篇无关课程作业，不属代码库）
- ✅ 合并 `CLAUDE.md` + `.windsurfrules` → 统一 `AGENTS.md`（旧双 AI 分工模式废弃）
- ✅ 精简 `PROJECT_CONTEXT.md`（旧 460 行含编造指标/过时规划 → 精简校正版）
- ✅ `docs/research.md` 顶部加"未核实警告"；`docs/INDEX.md` 重建索引
- ✅ 新增 `docs/planning/`：客观评估报告 + CCF-C 论文可行性与排期 + v2 架构重构设计
- ⚠️ 明确作废旧文档"15 样本 / 100% 检出 / 0% 误报"等编造指标

### 2026-07-18 — M4 动态引擎最小闭环（Devin）

- ✅ 新增 `src/dynamic_engine/`：honeypot（蜜罐随机标记假凭据）+ harness（沙箱内 `sys.addaudithook` 行为探针）+ sandbox（Docker `--network none` 沙箱 + 子进程兜底）+ monitor（行为研判打分）+ pipeline（`audit_dynamic()`）
- ✅ 已接入 `static_engine/pipeline.audit_skill(enable_dynamic=True)`，综合评分升级为静态/动态/LLM 三引擎加权（0.4/0.35/0.25，未启用自动归一化），无 Docker 时优雅降级
- ✅ 新增 `tests/test_dynamic_engine.py` 22 个测试（含 Docker 集成测试，skipif 保护）；全套 78 passed + 10 skipped
- 🔄 待补：mitmproxy 流量解密、libfaketime 48h 延迟激活、多次执行行为对比、非 Python 载荷

### 2026-07-18 决定：Hermes 已完全弃用并清理 ❌

**核心决定**：
1. **Hermes Agent 彻底下线**：已从项目中删除 `docs/hermes_setup.md`，并彻底清除了 D 盘的 `hermes_data` 和 `hermes_workspace` 目录。释放了 1.3GB+ 的本地磁盘空间。日常开发与调试工具全部由现代化 AI 助手（如 Antigravity）直接进行联网搜索与爬取。
2. **下一步选定 M3 选项 B**：把 MiMo LLM 接入 `pipeline.audit_skill()`，跑 15 样本（10 恶意 + 5 正常）拿**联合检出率/误报率**第一手数据。

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

---

## 2026-07-18 P0：数据集 + 评测框架（方向 A）

> ⚠️ **作废声明**：本文件上方"量化指标目标 vs 当前"里的
> "SKILL.md 恶意检出率 100%（10/10）/ 静态误报率 0%（0/5）"等数字，
> 系早期小样本/编造指标，**一律作废，不得写入论文**。以下为真实、可复现的进展。

### 已完成（本地已验证，非编造）
- **MalSkillBench 数据加载器** `src/data_ingestion/malskillbench_loader.py`：
  解析技能文件夹 → 统一 `MalSkillSample`；从文件夹名解析三维分类（向量 CI/PI/MIXED ×
  行为 B1–B15 × 插入策略），识别 B10–B15 = agent 控制面难子集。
  实测统计：**恶意 3,944 + 良性 4,000 = 7,944**，SKILL.md 缺失 0。
- **评测框架** `src/evaluation/`：
  - `metrics.py`：P/R/F1/FPR/Accuracy + 混淆矩阵（正类=恶意），纯计算可复用。
  - `malskillbench_baselines.py`：调用 MalSkillBench 官方汇总脚本复现 baseline 对照表。
- **Baseline 复现**（来源 MalSkillBench，须注明）：现有工具普遍"高精度低召回"或"高召回高误报"，
  最佳技能安全 LLM 扫描器 F1≈0.81–0.89 但误报 15%–37%。详见
  `docs/planning/baseline复现结果_MalSkillBench.md`。
- 测试：数据加载器 + 评测框架共新增 21 测试，全过，ruff 干净。

### 下一步
- 声明能力抽取（SKILL.md → declared capabilities）静态 + LLM。
- 声明 vs 运行时观测 的类型化一致性比对（接现有 dynamic_engine + 蜜罐）。
- agent 控制面 B10–B15 子集的 baseline 逐样本重算。
- 50 恶意 / 50 良性 端到端小批 sanity check。

## 2026-07-18 方法核心：声明-观测一致性核验 + 决策（方向 A）

### 已完成（本地已验证，含真实 Docker 端到端）
- **统一能力分类学** `src/conformance/capabilities.py`：7 类能力（network/file_read/file_write/
  subprocess/dynamic_code/credential_access/identity_write），声明侧与观测侧共用；
  提供 `normalize_declared()`（声明字符串→能力）与 `observed_from_audit/events()`（沙箱观测→能力）。
- **一致性核验** `src/conformance/conformance.py`：
  类型化比对 undeclared = observed − declared、unused = declared − observed；
  未声明敏感能力加权 + 蜜罐命中(canary)确凿证据 → 确定性、可解释的 allow/review/deny 决策
  （identity_write 权重最高，命中蜜罐一律 deny）。
- **端到端管线** `src/conformance/pipeline.py`：SKILL.md→声明抽取→带蜜罐 Docker 沙箱观测→核验→决策。
- **真实 Docker 冒烟**（`scripts/e2e_smoke_conformance.py`，仅自写合成代码，非真实恶意样本）：
  - 良性 `print` → executed, deviation=0.00, **DECISION=allow**；
  - "读蜜罐 OPENAI_API_KEY 并 urllib 外传"模拟 → **honeypot_triggered=True**，
    undeclared={credential_access, network}, deviation=1.00, **DECISION=deny**。
  断网(--network none)拦住真实传输，但"读凭据+外传企图"被审计钩子+蜜罐标记坐实。
- 测试：conformance 13 + 端到端 Docker 2（skipif 保护），全过；全量 114 passed + 10 skipped，ruff 干净。

### 下一步
- agent 控制面 B10–B15 子集的 baseline 逐样本重算（凸显 SOTA 崩点）。
- 在真实 MalSkillBench 样本上跑 50 恶意/50 良性小批（隔离容器，谨慎执行 CI 类可执行样本；
  PI 类无可执行代码的走"声明+静态+LLM"路径），产出初步 P/R/F1 与决策分布。
