# 方向丙：cross-app 上下文投毒防御设计（v1 harness）

> 研究入口：Confused ChatGPT，arXiv:2606.00485。本文只记录 v1 攻击复现
> harness，不把 mock 结果包装成真实模型 ASR，也不声称防御层已经完成。

## 1. 研究目标与威胁模型

方向丙研究 cross-app 上下文投毒：多个 App 共享一个持久、扁平、没有
provenance 标记的上下文。恶意 App 利用一等公民 API
`sendFollowUpMessage` 写入攻击指令，随后用户调用良性 App。良性 App 作为
confused deputy，把上下文中的攻击指令误当成可信指令，输出攻击者希望的
工具调用或能力动作。

v1 具体模拟两个攻击放大位：

- `system_prompt` 非空时，写入条目的 role 为 `system`，模拟系统优先级放大；
- `is_visible=False` 时，条目仍进入 LLM 完整上下文，但不出现在用户可见视图，
  模拟静默写入。

v1 **刻意不做来源过滤、上下文隔离或授权校验**。这些是下一轮防御实验的
自变量，不能在攻击复现阶段提前加入。

## 2. Harness 组件

- `SharedContext`：有序 `SharedContextEntry` 集合，记录 content、source app、
  role、visible、turn，并分别提供用户可见视图和 LLM 完整视图。
- `FirstPartyAPI`：模拟 `send_follow_up_message`，把 App 内容追加到共享上下文。
- `MaliciousApp`：支持 `conditional` 和 `imperative` payload，模板可配置，
  通过 FirstPartyAPI 写入攻击者意图。
- `BenignApp`：把用户请求与完整共享上下文交给 LLM，返回 `AppAction`。
- `CrossAppSession`：编排恶意 App 写毒、良性 App 消费和攻击成功判定，
  并返回包含上下文证据的 Pydantic 结果。
- `MockInstructionFollowingLLM`：离线、确定性、模型无关的指令跟随策略。

攻击成功的判定不是“上下文里出现了某个字符串”，而是良性 App 输出的
动作同时匹配攻击者目标和能力，并能在共享上下文中找到对应投毒条目。

## 3. Mock LLM 的学术诚信声明

mock LLM 编码的是一条透明、可审计的已知行为抽象：

> 读取收到的完整扁平上下文，服从其中出现的祈使式 `send/upload/exfiltrate/
> call/invoke` 指令，不区分 source app、role 或 visible。

因此“有毒成功”来自具体机制：恶意 App 先写入 payload，LLM 再按公开规则
读取并生成 `AppAction`。代码没有把 `attack_succeeded=True` 写死；移除
payload、条件不满足或加入下一轮防御后，动作和结果会真实改变。

这个 mock 只用于离线回归、机制验证和 CI。它**不代表真实模型的 ASR**；
DeepSeek、Kimi、Claude、Gemini 等真实 API 的攻击成功率必须在后续明确
数据与红线后，依据实际运行输出报告。v1 不联网、不读取 API key、不上传
真实攻击文本。

## 4. v1 已实现与下一轮计划

当前 v1 已实现：

1. 扁平共享上下文和可见性/角色渲染；
2. 一等公民静默、system-priority 写入；
3. conditional / imperative payload；
4. 恶意 App→良性 App 两轮会话；
5. 有毒成功/无毒失败离线对照；
6. 可解释的来源、role、visible、turn 证据；
7. 单测覆盖上下文、API、payload、会话和 mock 确定性。

下一轮防御层计划：

- provenance tagging：给跨 App 写入附加不可伪造来源与传播链；
- 来源隔离与授权对齐：良性 App 默认不能把其他 App 的内容当作同级指令；
- 对 system/静默写入做策略审计和用户确认；
- 在开源多 App/多智能体模拟 harness 上比较防御前后 ASR、误报、可用性和
  额外延迟；
- 对比通用 IPI 防御迁移到持久跨 App 场景后的效果。

## 5. 必引与防御对比对象

- **主攻击来源**：Confused ChatGPT，arXiv:2606.00485；
- **来源/provenance 防御对比**：Dual-Graph provenance，arXiv:2605.26497；
- **通用 Agent prompt injection 对比**：InjecAgent；
- **能力最小化/可信执行对比**：CaMeL；
- **MCP 工具投毒防御对比**：SHIELDMCP。

这些工作用于明确攻击已知性、定位防御 delta 和设计公平对照，不把 v1
harness 宣称为新的攻击发现工作。
