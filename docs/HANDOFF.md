# 交接书（换账号 / 新会话快速上手）

> 本文件专为「**换 AI 账号 / 新开对话**」而写。目标：任何 AI 工具（Devin / Antigravity /
> Claude Code / Cursor …）clone 本仓库后，读完本文件即可**无缝续上项目路线**，不依赖任何聊天记录、
> 也不依赖上一个账号所在组织的 Devin Playbook/Knowledge（那些**跨组织不继承**）。
>
> 唯一可靠的记忆载体 = **本 GitHub 仓库**。凡是没合并进 `main` 的东西（本地补丁、`runs/` 产物、
> 聊天上下文）在换账号后一律丢失，务必先确认关键成果都已进 `main`。

---

## 0. 给新 AI 的开场白（可直接复制粘贴给新会话）

```
这是一个正在进行的科研项目「影刃卫士 ShadowBlade Guardian」。请严格按顺序先读这些文件再动手：
1) AGENTS.md（协作/编码/学术诚信硬规则）
2) docs/HANDOFF.md（本交接书：现状/路线/下一步/红线）
3) docs/INDEX.md（知识库索引 + 快速上下文）
4) docs/progress.md 顶部「⭐当前主线」
5) docs/planning/小批实验结果_方向A.md（真实实验数字与诚实归因）

读完后用 3~5 句话向我复述：研究主线是什么、当前真实指标是多少、下一步该做什么、有哪些红线。
复述正确我们再继续。不要相信任何"高召回/100%检出"之类的漂亮数字，一切以仓库 committed 文档为准。
```

---

## 1. 项目一句话

面向 **AI Agent Skills（`SKILL.md` / ChatGPT Apps）** 供应链与运行时安全的**审计与防御研究系统**，
目标产出**可复现、可发表**的方法与实验（现实定级 **CCF-C / 中文核心 / SCI Q3–Q2**，先挂 arXiv preprint 占位）。

核心方法：**per-run 随机蜜罐 / canary 污点取证**——隔离沙箱真实执行 + 运行时行为监控（`sys.addaudithook`）
抓凭据窃取/外传的"现行"，再与**声明能力**比对，做**确定性、可解释**的 `allow / review / deny`。

## 2. 研究主线（已锁定 A+B）

- **方向 A（保底·有公开数据）**：运行时接地的能力一致性核验 + 蜜罐取证 + 阻断。基于公开数据集
  **MalSkillBench**（3,944 恶意 + 4,000 良性，自带 baseline），专打 SOTA 检测器崩掉的
  prompt-injection / agent 控制面攻击（行为标签 B10–B15）。区别于 BIV 的"静态预测"——我们是"运行时观测"。
- **方向 B（新颖·需自建）**：跨 App 共享上下文投毒的检测/防御/基准（ChatGPT Apps SDK 场景），
  迁移同一套 canary 污点方法。**B 不阻塞 A**；先把 A 做扎实保底，再做 B 拉上限。

## 3. 当前真实状态（诚实，勿夸大）

- ✅ 已通：数据加载器 + 评测框架(P/R/F1/FPR) + baseline 复现 + 声明能力抽取(`allowed-tools`) +
  声明↔观测一致性核验 + 决策 + 动态沙箱(Docker `--network none` + 蜜罐 + 审计钩子 + 依赖兜底 shim) + 端到端管线。
- 🔬 **真实 50/50 小批当前指标**：**Precision=1.00 / FPR=0.00 / Recall=0.16 / F1=0.28 / 蜜罐命中=0**
  （TP=8, FP=0, FN=42, TN=50）。定位 = **高精度、零误报、低召回的"确认层"**，不是要取代最强扫描器。
- ✅ **诱饵扩展(v2)**：蜜罐诱饵扩到 ~20 个（加密钱包/助记词、浏览器登录数据/Cookie、AWS/云/开发者凭据）+
  "读敏感凭据即映射 `credential_access`"信号。机制经合成样本验证正确。
- ✅ **入口触发(v3)**：harness 跑完模块顶层后主动调用样本自定义、可无参调用的入口函数（仍在 Docker 隔离内）。
  经合成 + Docker 单测验证正确（函数门控型窃密样本能抓到→deny）。
- ⚠️ **v2/v3 都没有提升那批 50/50 的召回**（仍 R=0.16、蜜罐=0）。**这是真实结果，不得包装成"召回提升"。**
  逐样本诊断（真实数字）：50 个恶意样本里 **7 个 SyntaxError**（无法编译）、**16 个运行即崩**（缺第三方库 /
  Windows 路径与命令 / NameError）、18 个产生可观测敏感行为——其中 ~10 个的敏感能力（Bash/WebFetch）是样本
  **如实声明**的，一致性核验按设计放行。瓶颈已从"函数没被调用"转移为"**样本在通用 Linux 沙箱跑不起来**"
  和"**纯能力粒度的固有盲区**"。详见 `docs/planning/小批实验结果_方向A.md` 第 5 / 5b 节。

## 4. 下一步（按优先级，均不涉及编造数据）

1. **可疑外传目标信誉（最高杠杆）**：网络能力即便"已声明"，只要外联到 discord CDN / telegram / rentry /
   pastebin raw / 硬编码 IP 等**信誉可疑目标**，仍作为强信号。预期打掉那 ~10 个"声明广权限但外传恶意目标"的
   样本，而良性几乎不碰这些目标 → **有望在保持 FPR=0 的前提下真正提召回**。
2. **样本可执行性**：为 Windows 定向 / 缺库 / 语法非法样本提供更贴近其预期环境的执行路径，或明确将这部分
   划归静态/LLM 路径、不计入运行时召回分母。
3. 更大规模 pilot → 消融实验 → MaliciousAgentSkillsBench 跨数据集泛化。
4. 方向 B：开源"多 App 共享扁平上下文"测试台 + 跨 App 投毒防御基准。
5. 论文初稿 + arXiv preprint。

## 5. 红线（务必遵守，违反即学术/安全事故）

- **学术诚信**：不得编造任何实验数据、检出率、样本数量、F1。没真跑出来的一律不写。外部文献/arXiv 编号/
  竞品数字须逐条核实后才引用。**PR 描述里的数字一律以仓库 committed 的实验文档为准**（历史上自动生成的
  PR 描述多次编造"高召回"，已被纠正——见 PR #6、#8）。
- **安全**：真实恶意样本**只在 Docker 隔离沙箱执行**（`--network none` + 内存/CPU/PID 限制 + 临时工作区、
  执行后删除），绝不在宿主机跑；不上传真实恶意样本到闭源云 API；不提交任何密钥/token/凭据。
- **不碰用户私有文件**：`models/qwen3-4b-awq/tokenizer.json` **永远不要**纳入任何提交/补丁/PR。
- **数据集不入库**：`datasets_external/`、`runs/` 已 gitignore，不提交、不重分发。
- **改测试**：不得为提高指标而修改测试或伪造结果；发现测试/任务不合理应指出，而非绕过。

## 6. 协作方式（重要：Devin 对本仓库无 push 权限）

- 目前 Devin 直接 push GitHub 会 **403**。因此工作流是：Devin 在本地改代码 → `git format-patch` 生成补丁 →
  用户拿补丁到 **antigravity** 执行 `git am` 并 push、开 PR → 用户把 PR 链接发回来让 Devin 核对。
- 给 antigravity 的标准话术（示例）：
  ```
  在 ~/shadowblade：
  git checkout main && git pull
  git checkout -b <分支名>
  git am <补丁文件>.patch      # 若报错改用: git apply <补丁>.patch && git add -A && git commit -m "[模块] 描述"
  git push -u origin <分支名>
  然后开 PR 到 main，标题 [模块] 简要描述，把链接发我
  ```
- 规则：不直接 push `main`；不同 AI/人不同时改同一文件；改完代码更新 `docs/progress.md`，改完文档/数据在
  `docs/INDEX.md`「最近变更」留摘要；commit 格式 `[模块] 简要描述`；**代码必须写中文注释**。

## 7. 环境与复现要点

- 语言 Python；类型注解 + Pydantic；本地模型 Qwen3-4B AWQ(vLLM)，云端可用 OpenAI/Anthropic/DeepSeek(LiteLLM) 做对比。
- 已知环境问题：`tests/test_rag_knowledge.py` 依赖可选包 `chromadb`，未装时全量 `pytest` 收集会报错——
  与主线改动无关，跑测试时可 `--ignore=tests/test_rag_knowledge.py`；Docker 集成测试无 Docker 会自动 skip。
- 真实小批复现：`PYTHONPATH=. python scripts/run_pilot_batch.py --n 50 --seed 20260718 --timeout 20 --out runs/pilotXX.json`
  （会在 Docker 隔离内执行真实恶意代码，确保 Docker 可用）。

## 8. PR 历史速查

- #4 方向文档；#5 数据加载+评测/baseline+一致性核验方法核心；#6 依赖兜底 shim+allowed-tools+真实小批(v1)；
  #7 门面/记忆文件同步 A+B 主线；#8 诱饵扩展(v2)+读凭据信号；#9 入口触发(v3)+诊断。
- 均通过 antigravity 补丁流程提交；#4–#8 已合入 `main`，#9 视合并状态而定（新会话请以 `git log origin/main` 为准）。
