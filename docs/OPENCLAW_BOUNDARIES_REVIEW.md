# nanoagent 从 OpenClaw 借鉴的架构边界 Review

> 文档性质：讨论 nanoagent 值得从 OpenClaw 借鉴的分层边界，以及不应提前复制的产品复杂度。
>
> 第一部分保留原始建议；第二部分追加结合 nanoagent 当前设计与 OpenClaw 官方资料的评审意见。本文只讨论架构边界，不构成下一版本的完整实现设计。

## 一、原始建议

建议在 nanoagent 中形成三层，而不是把所有东西继续塞进 AgentLoop + Hook：

```text
nanoagent-core
  Message / Context / LLM / Tool
  AgentLoop
  核心 Hook 与策略契约

nanoagent-runtime
  SessionStore
  ContextEngine
  ToolPolicy / Approval
  RunEvent / Cancellation
  Task / Resume
  Sandbox Adapter

nanoagent-app
  CLI / API / Bot / Gateway
  Cron / Channel
  Deployment
```

如未来确实需要运行 Codex、Claude Code 等原生 Agent，再额外增加：

```text
TurnExecutor / AgentRuntime

supports(prepared_turn)
run_attempt(prepared_turn) -> event stream
```

内置 AgentLoop 是其中一个 Executor，Codex 之类是另一个。

但在出现真实需求之前，不要为了对标 OpenClaw 提前加入 Harness Registry、Gateway、Node Protocol 和多渠道系统。

---

## 二、Architecture Review

### 1. 总体判断

这个分层方向合理，而且比继续扩充 AgentLoop + Hook 更能保护 nanoagent 的核心边界。

最值得借鉴的不是 OpenClaw 已有多少模块，而是它实际暴露出的三类职责不能长期混在一起：

- 模型与工具循环；
- Session、Task、事件、取消和审批等有状态运行语义；
- Channel、Gateway、Cron、部署和外部客户端等产品接入语义。

OpenClaw 官方 Gateway 协议已经同时覆盖 Session、Task、取消、审批、工具策略、Channel 和 Node 等能力；这说明它是完整产品控制面和运行入口，而不只是 Agent Loop。nanoagent 当前没有材料证明自己需要承担同等产品范围，因此适合借鉴分层，不适合照搬模块数量。[OpenClaw Gateway Protocol](https://github.com/openclaw/openclaw/blob/main/docs/gateway/protocol.md)

核心结论是：

> nanoagent 应先把“执行内核、持久运行、应用接入”分开，再根据真实需求决定是否增加外部 Agent Runtime；不应先复制 OpenClaw 的 Gateway 和多渠道体系。

### 2. 三层职责基本合理，但先做代码边界，不急于拆发行包

建议先在单一代码库中形成：

```text
nanoagent/
  core/
  runtime/
  app/
```

而不是立即拆成三个独立 PyPI 包。

原因是当前需要验证的是依赖方向和职责边界，不是独立发布。过早拆包会增加版本联动、兼容矩阵和安装复杂度，却还没有第二个应用或 Runtime 实现证明独立发布的收益。

拆层后的依赖方向应保持：

```text
app → runtime → core
```

并明确禁止：

- core import runtime 或 app；
- runtime import CLI、Bot、Channel 或具体 Gateway；
- app 绕过 runtime 直接修改 SessionStore、Policy 状态或执行 Tool。

当三个层次真的出现独立版本节奏或外部复用者时，再升级为独立发行包。

### 3. nanoagent-core：保留执行原语，不承担持久生命周期

原建议把以下内容放在 core 是合理的：

- Message、ToolCall、ToolResult 等值对象；
- LLM 与 Tool 能力契约；
- 最小 AgentLoop；
- Runtime 实现需要共同遵守的核心协议。

但当前 `Context` 的含义需要重新校准。现有 Context 同时承担：

- append-only 对话历史；
- usage；
- summary；
- 模型 view；
- metadata 扩展点。

如果 ContextEngine 进入 runtime，core 中的 Context 不应继续演化成 Session、RunState 和任意运行数据的容器。否则名义上拆层，状态仍会通过 `Context.metadata` 回流 core。

更清晰的边界是：

- core 保存模型与工具循环需要的最小 Turn / Message 数据；
- runtime 保存 RunState、Task State、Working Set、Checkpoint 和完整事件；
- ContextEngine 从 runtime 状态生成本轮模型输入；
- AgentLoop 消费准备好的输入并产生结构化执行事件。

是否重命名当前 Context，可以在 vNext 接口设计时决定；这里需要先确定的是职责，而不是提前决定类名。

### 4. nanoagent-runtime：这是下一阶段真正需要建设的层

原建议列出的 SessionStore、ContextEngine、ToolPolicy、Approval、RunEvent、Cancellation、Task 和 Resume，都属于同一层：它们共同管理“一次执行如何跨轮、跨中断和跨进程保持连续”。

建议进一步明确每项回答的问题：

- **SessionStore**：对话或任务身份如何持久化、并发读写和版本控制；
- **ContextEngine**：RunState、历史、Memory 和 Evidence 如何投影成本轮输入；
- **ToolPolicy / Approval**：副作用执行前如何决策，等待审批时 Run 如何暂停；
- **RunEvent**：发生过什么，是 Trace、恢复和审计的共同事实；
- **Cancellation**：外部取消如何进入状态机，并传播到模型、工具和子任务；
- **Task / Resume**：执行游标、租约、重试和恢复边界如何保存；
- **Sandbox Policy**：什么动作应在哪种隔离环境执行。

其中 “Sandbox Adapter” 需要再分一层：

- Sandbox 的选择、权限和路由决策属于 runtime；
- Docker、远程 Sandbox、SSH 或其他具体后端实现属于 adapter / plugin。

否则 runtime 会直接依赖具体基础设施，破坏可替换性。

### 5. nanoagent-app：保持入口与交付语义，不反向定义 Runtime

CLI、API 和 Bot 明确属于 app。Gateway、Cron、Channel 和 Deployment 也可以放在这一层的长期范围中，但不代表 nanoagent 近期需要实现它们。

它们与 runtime 的关系应是：

- app 提交 Run、订阅 Event Stream、发送 Cancel / Approval；
- runtime 执行状态机并返回结构化事件；
- app 负责把这些事件转换为终端输出、HTTP、WebSocket 或消息平台事件；
- app 不定义 Tool 权限语义，也不自行拼接可恢复状态。

OpenClaw 的官方 Gateway CLI 文档明确把 Gateway 定义为承载 channels、nodes、sessions 和 hooks 的 WebSocket server，这属于产品运行入口，而不是通用 Agent 内核。[OpenClaw Gateway CLI](https://github.com/openclaw/openclaw/blob/main/docs/cli/gateway.md)

因此 nanoagent 暂时只需要保证 runtime 有稳定 API，不需要为了“层次完整”提前实现 Gateway。

### 6. TurnExecutor / AgentRuntime 是正确的扩展缝，但不应现在落地

把内置 AgentLoop 与 Codex、Claude Code 等原生 Agent 放到统一 Executor 抽象下，方向上合理：

```text
nanoagent Runtime
  → Embedded AgentLoop Executor
  → External Native Agent Executor
```

OpenClaw 官方资料已经展示了类似需求：ACP bridge 把外部客户端 Session 映射到 Gateway Session，将 Gateway 流式事件转换为 ACP 更新，并把 cancel 映射到当前 Run 的 abort。官方文档同时承认，历史 Tool/System 事件无法完整重建、多个客户端共享 Session 时 cancel 路由只是 best-effort。这些限制说明，外部 Agent 接入真正困难的是 Session、Event 和 Cancellation 语义，不是简单调用一个 CLI。[OpenClaw ACP Bridge](https://github.com/openclaw/openclaw/blob/main/docs.acp.md)

但当前 nanoagent 只有一个内置 AgentLoop，没有第二个 Executor 的真实接入需求。此时直接抽象 `TurnExecutor`，很容易根据想象设计出错误接口。

更稳妥的顺序是：

1. 先完成 nanoagent-runtime 的 Run / Event / Cancellation 基础；
2. 保持内置 AgentLoop 可以被 adapter 包装；
3. 出现第一个真实外部 Runtime 接入时，用两种实现共同反推最小协议；
4. 再把协议固化为公共契约。

因此，“保留扩展缝”现在是设计原则，“创建 Executor Registry”还不是当前任务。

### 7. proposed Executor 接口还缺少执行所有权

原始接口：

```text
supports(prepared_turn)
run_attempt(prepared_turn) -> event stream
```

表达了能力匹配和流式执行，但没有回答最关键的问题：

> Tool 是由 nanoagent Runtime 执行，还是由外部原生 Agent 自己执行？

这会直接影响 Permission、Approval、Sandbox 和审计能否统一。

至少存在两种模式：

```text
RUNTIME_MANAGED_TOOLS
  Executor 只产生 ToolRequest
  nanoagent 做 Policy / Approval / Sandbox / Execution

EXECUTOR_MANAGED_TOOLS
  Codex / Claude Code 等原生 Runtime 自己执行 Tool
  nanoagent 只能通过其原生权限接口约束或观察
```

如果外部 Executor 自己执行工具，却仍宣称所有动作都经过 nanoagent ToolPolicy，会形成错误的安全承诺。Executor 能力声明至少需要表达：

- Tool execution ownership；
- 是否支持 cancel；
- 是否支持 resume；
- 是否支持 approval interception；
- 是否提供结构化 Tool Event；
- Session 是一次性还是可持久复用；
- 是否允许 nanoagent 注入 Sandbox / working directory；
- Event 是否能稳定关联 run、turn 和 tool call。

`supports(prepared_turn)` 可以基于这些 capabilities 判断是否兼容，但不能只判断模型输入格式。

### 8. PreparedTurn 与 Event Stream 应是跨 Executor 的最小公共语义

如果未来确实引入 Executor，`PreparedTurn` 不应携带整个 nanoagent Runtime 内部对象，而应是版本化、只读的执行请求，例如：

```text
PreparedTurn
  run_id / turn_id
  session_ref
  messages
  tool descriptors
  working directory / artifact refs
  budget / deadline
  policy context ref
  requested capabilities
  schema_version
```

Event Stream 也不应直接透传不同 Agent 的私有日志，而应归一成最小事件族：

```text
TurnStarted
ModelOutputDelta
ToolRequested
ToolStarted
ToolCompleted
ApprovalRequested
ArtifactProduced
UsageUpdated
TurnCompleted
TurnFailed
TurnCancelled
```

原生 Agent 特有事件可以保留 namespaced extension，但 Runtime 的状态推进只能依赖公共事件，不能依赖 Codex 或 Claude Code 的私有字符串日志。

这套事件契约只有在第二个 Executor 出现时才值得定稿；当前可以先让内部 RunEvent 保持可映射性。

### 9. 不应提前复制的 OpenClaw 复杂度

原建议对范围的克制是正确的。官方资料显示 OpenClaw Gateway 已经覆盖：

- 多 Channel 与消息投递；
- Session 管理和订阅；
- Task ledger 与取消；
- Node 配对和远程调用；
- Cron；
- Approval；
- Plugin；
- Tool catalog 与调用入口；
- Talk / realtime；
- Gateway 配置与控制 UI。

这些能力来自 OpenClaw 的产品定位，不是所有 Agent Runtime 的必备组成。[OpenClaw Gateway Protocol](https://github.com/openclaw/openclaw/blob/main/docs/gateway/protocol.md)

对 nanoagent 而言，目前没有依据支持提前建设：

- Harness Registry；
- 通用 Gateway；
- Node Protocol；
- 多 Channel Router；
- 设备配对；
- 分布式控制面。

它们的共同代价是引入长期兼容协议、身份与授权模型、部署状态和大量集成测试。一旦进入公共接口，后续很难收回。

nanoagent 当前只需确保：

- runtime API 不绑定 CLI；
- Event Stream 可被未来 API / Bot 消费；
- Session ID 和 Run ID 不依赖单进程；
- Tool / Sandbox adapter 可替换；
- 外部 Executor 有可插入的位置。

这已经足以保留未来可能性。

### 10. 建议的落地顺序

结合当前运行闭环缺口，建议按以下顺序推进：

```text
第一步：形成目录和依赖边界
  core / runtime / app
  暂不拆独立发行包

第二步：建设单 Agent Runtime
  Run / Session / Event
  ToolPolicy / Approval
  Cancellation / Resume
  ContextEngine

第三步：让现有 AgentLoop 通过 Runtime 执行
  验证 CLI 只依赖 runtime API
  验证中断、审批和恢复

第四步：出现真实外部 Agent 需求
  接入一个 Codex 或 Claude 类 Runtime
  用两个实现反推 TurnExecutor 最小协议

第五步：只有出现产品需求时
  增加 Gateway / Cron / Channel / Deployment
```

### 11. 验收边界

三层拆分是否成立，不看目录名称，而看以下行为能否成立：

- core 测试不依赖数据库、网络、任务队列和 CLI；
- runtime 可以替换 SessionStore 和 Sandbox 后端；
- CLI 通过 runtime API 启动、取消和恢复 Run；
- ContextEngine 不通过修改 core metadata 偷渡状态；
- ToolPolicy 对内置 AgentLoop 的所有副作用调用生效；
- app 层移除后，runtime 仍可独立运行；
- 未实现外部 Executor 时，不存在空壳 Registry 和假扩展点。

### 12. 最终结论

这份建议最合理的部分是“借边界，不借规模”。

应当采纳：

1. 将 nanoagent 分成 core、runtime、app 三个职责层；
2. 将 Session、ContextEngine、Policy、Event、Cancellation 和 Resume 从 AgentLoop / Hook 中剥离到 runtime；
3. 为未来原生 Agent 保留 Executor 扩展方向；
4. 用真实的第二个 Executor 反推公共协议，而不是现在凭想象定稿。

需要补充的核心约束是：

> 外部 Agent Runtime 接入时，必须显式声明 Tool 执行所有权和可治理能力；否则 nanoagent 无法保证统一的 Permission、Approval、Sandbox 和审计语义。

不应采纳的是为了对标 OpenClaw 而提前复制 Gateway、Node、Channel 和 Registry。根据当前材料，这些能力没有直接需求依据，只会扩大协议面和维护成本。
