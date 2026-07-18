# 开发进度

> 最后更新：2026-07-18（**Hermes 已完全弃用与清理**，焦点回归 M3 静态引擎与 M4 动态沙箱）

## 当前状态：M2 → M3 过渡（静态全链路打通）+ M4 动态引擎最小闭环已落地

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
