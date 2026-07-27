# nanoagent 当前运行闭环缺口 Review

> 文档性质：针对 nanoagent 当前设计与演进顺序的专项 Review。
>
> 第一部分保留原始 Review 判断；第二部分追加基于当前 `docs/DESIGN.md` 与代码契约的评审意见。本文不替代当前实现设计，也不直接修改既有路线图。

## 一、原始 Review

### 1. “核心永远不改”承诺过强

目前提前预留 Hook、`view()` 和字段是合理的，但以下需求都可能反过来影响核心契约：

- Streaming event；
- Cancellation / interrupt；
- 并行 Tool Call；
- 人工 Approval 后恢复；
- Durable resume；
- Native Agent runtime；
- Tool 参数重写；
- Background Task；
- Subagent 状态传播。

更稳的表述应从：

> core 一行永远不改

调整为：

> 核心职责稳定，公共契约采用兼容演进和版本管理。

否则为了维护“不改”这个目标，未来可能把本应属于核心语义的状态塞进 metadata 或 Hook 副作用里。

### 2. Permission 不应该排在 MCP 之后

目前路线是：

```text
v0.2：Skill / OTel / MCP
v0.3：Permission / Circuit Breaker / Subagent
```

如果 v0.2 接入 MCP，工具数量、来源和权限范围都会扩大，而权限仍是 AllowAll，这个顺序不合理。

建议调整为：

```text
v0.2：
  基础 Tool Policy
  Permission Decision
  OTel
  Skill
  MCP

v0.3：
  Context pruning / compaction
  Durable session / event stream / cancellation
  Circuit breaker

v0.4：
  Durable task + Subagent
  Eval
```

至少应让基础 Permission 与 MCP 同版本落地。

### 3. ToolDecision 只有 Allow / Deny 不够

可以参考 OpenClaw，把决策扩展为：

```text
ALLOW
DENY
ASK
MODIFY
```

并携带：

- `reason`
- `rewritten_arguments`
- `risk_level`
- `execution_target`
- `approval_timeout`

这样 PermissionStrategy 才能覆盖：

- 直接拒绝；
- 参数清洗；
- 危险操作人工确认；
- Host / Sandbox 路由；
- 超时默认拒绝。

不必把沙箱实现放进 core，但 core 的执行契约需要能表达这些结果。

### 4. Skill 定义建议收窄

当前把 Skill 定义成：

> 一组工具 + Prompt + 元数据

这会混淆“行为能力”和“使用说明”。

建议改成：

```text
Tool
  可调用动作

Skill
  渐进加载的指令、说明、模板和资源
  可以引用 Tool，但不拥有 Tool 的执行语义

Plugin / Bundle
  用于打包 Tool + Skill + Hook + Adapter
```

这样更接近 OpenClaw、Claude/Codex 一类生态当前正在形成的公共语义，也有利于 MCP Tool 与 Skill 正交。

### 5. Subagent 不能只有 spawn_subagent Tool

把 Subagent 暴露成工具是正确的模型侧接口，但下面仍然需要 Runtime 支撑：

- 独立 Context / Session；
- Run ID；
- 状态机；
- 取消；
- 超时；
- 结果回传；
- 工具权限收缩；
- 并发上限；
- 父子关系；
- 失败和孤儿恢复。

OpenClaw 每个 Subagent 都对应一个 Session 和后台 Task，说明 Subagent 本质上首先是 Durable Run，其次才是一个 Tool。

所以 nanoagent 应先完成 Run / Session / Event 基础设施，再实现真正 Subagent。

---

## 二、Architecture Review

### 1. 总体判断

这五个判断整体成立，而且共同指向同一个底层缺口：

> nanoagent 当前已经有最小 ReAct 执行能力，但还没有把执行生命周期、权限决策、中断恢复和派生任务组织成完整的运行闭环。

其中第 1、2、5 点不是局部功能调整，而是在校准路线图的依赖顺序：

```text
Tool governance
→ Run / Event / Interrupt 基础
→ Durable execution
→ Subagent
```

如果顺序反过来，MCP 会先扩大工具暴露面，Subagent 会先扩大执行并发和状态空间，Runtime 却仍只有 AllowAll 和内存 Context，后续只能通过特殊分支补洞。

### 2. 对“核心稳定”的判断：同意，但应稳定语义而非冻结形状

当前设计提前预留 Hook、`Context.view()`、`pinned` 和 `token_estimate`，对上下文裁剪这一类扩展是有效的。这部分判断不需要否定。

问题在于，现有文档从“上下文压缩可以不改 core”进一步推导出“后续能力均不改 core”，证据并不充分。Streaming、Cancellation、Approval Resume、并行执行和 Durable Run 都会改变执行状态机或公共交互协议，不只是增加一个策略实现。

建议把 Stable Core 重新定义为以下稳定语义：

- 所有外部动作经过统一执行边界；
- 事实记录只追加，状态由事实派生；
- Policy 决策先于副作用执行；
- 模型可见上下文与完整执行历史分离；
- 能力实现依赖公共契约，Runtime 不依赖具体适配器；
- 公共契约允许增加兼容字段、扩展事件类型和按版本迁移。

“稳定”因此表示职责、依赖方向和核心不变量稳定，不表示类字段、Hook 数量和循环代码永久冻结。

还应区分两个容易混淆的概念：

- **Event Log**：持久事实源；
- **Event Stream**：把事件实时交付给 CLI、IDE 或外部消费者的接口。

前者解决恢复和审计，后者解决实时交互。可以共用事件模型，但不能因为有 Streaming API 就认为已经具备 Durable Resume。

### 3. 对 Permission 与 MCP 顺序的判断：同意，而且问题已经存在

基础 Permission 不仅应与 MCP 同版本，更应在 MCP 工具真正可执行之前完成。

原因不只在于 MCP 会扩大工具数量。当前 v0.1 已有 `run_shell` 等可能产生副作用的工具，而默认策略仍是 AllowAll；因此权限缺口在接入 MCP 之前已经存在。MCP 只是把这个缺口从本地内置工具扩大到多来源外部工具。

建议把 v0.2 拆成有依赖顺序的两个切片：

```text
v0.2a · Tool Governance Foundation
  Tool 风险与资源元数据
  Permission Decision
  参数校验与重写
  Host / Sandbox 执行路由
  决策与执行 Trace

v0.2b · Capability Expansion
  Skill 渐进加载
  MCP Adapter
  OTel 完整接线
```

这里的关键不是版本名称，而是门禁关系：

> 未经内部 Tool Contract 归一、权限决策和审计接线的 MCP Tool，不进入可执行注册表。

最小验收标准应包括：

- 未配置策略的外部 Tool 默认拒绝；
- 读取与写入权限能够区分；
- 原始参数、重写后参数和最终执行目标可审计；
- MCP Tool 与本地 Tool 经过同一授权路径；
- Policy 失败时，高风险写操作 fail-close。

### 4. 对 ToolDecision 的判断：方向正确，但四态并不完全互斥

`ASK` 和参数重写确实是当前 `allowed: bool` 无法表达的关键语义，`execution_target` 也为 Host / Sandbox 路由提供了必要接口。

但 `ALLOW / DENY / ASK / MODIFY` 作为同一个枚举存在层级混合：

- `ALLOW / DENY / ASK` 回答“是否执行”；
- `MODIFY` 回答“以什么参数执行”。

一次决策可能同时是“修改参数后允许”，也可能是“修改参数后请求审批”，因此 `MODIFY` 与另外三种并不互斥。

更清晰的契约可以是：

```python
class DecisionOutcome(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class ToolDecision:
    outcome: DecisionOutcome
    reason: str = ""
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    rewritten_arguments: dict | None = None
    execution_target: ExecutionTarget | None = None
    approval: ApprovalRequest | None = None
```

其中：

- `outcome` 是互斥控制结果；
- `rewritten_arguments` 是可选变换；
- `execution_target` 是执行路由；
- `approval_timeout` 应属于 `ApprovalRequest`，而不是所有 ToolDecision 的公共字段。

Runtime 还必须定义参数重写后的执行顺序：

```text
保留 original_arguments
→ Policy 产生 rewritten_arguments
→ 对 effective_arguments 重新做 Schema 校验
→ 必要时重新做资源级授权
→ 记录 original / effective / policy_version
→ 交给 Tool Executor
```

否则参数重写可能绕过最初授权依据。

### 5. Approval 不是扩展 ToolDecision 字段就完成

`ASK` 只表达“需要审批”，真正的 Human-in-the-loop 还需要 Run 状态机支持：

- Run 进入 `WAITING_APPROVAL`；
- 生成不可混用的 approval ID；
- 记录请求人、目标操作、参数、风险、过期时间和 Policy 版本；
- 审批响应写成事件；
- 恢复时确认 Tool 尚未执行；
- 如果等待期间参数、权限或策略已变化，重新校验；
- 超时按照明确策略拒绝或终止，不能隐式继续。

因此基础 Permission 可以先于完整 Durable Runtime 落地，但“暂停后恢复”的 ASK 语义必须依赖 Run / Event / Resume 基础。v0.2 若尚未具备恢复能力，可以先把 ASK 限制为同步前台审批，不能提前承诺后台可恢复审批。

### 6. 对 Skill 收窄的判断：同意，应把执行所有权留给 Tool

当前 `DESIGN.md` 明确定义 Skill 是“一组工具 + 提示词 + 元数据”。这会让 Skill 同时承担：

- 使用说明；
- 能力发现；
- 工具所有权；
- 打包分发。

这些职责在只有本地工具时还能共存；接入 MCP、Plugin 和外部 Registry 后，会出现同一个 Tool 被多个 Skill 引用、Tool 生命周期不属于任何单一 Skill、Skill 只提供流程说明但不提供新工具等情况。

建议采用以下边界：

- **Tool**：拥有输入输出、执行、副作用和权限语义；
- **Skill**：拥有渐进加载的说明、模板、资源、示例和 Tool 引用；
- **Plugin / Bundle**：拥有安装、打包、版本和分发关系，可以同时携带 Tool、Skill、Hook 与 Adapter。

Skill 可以声明 required tools、建议权限和适用条件，但这些只是引用与需求，不能覆盖 Tool Contract 或绕过 Runtime Policy。

这是一次术语和包结构调整，不只是文案修改。若采纳，需要同步修改 Skill manifest、加载流程和现有设计中的“Skill 属于 Tool 来源”表述。

至于这一术语是否已经成为 OpenClaw、Claude/Codex 等生态的统一公共语义，本文提供的材料不足以验证；nanoagent 可以采用这个边界，但不应把外部生态一致性作为已证事实。

### 7. 对 Subagent 的判断：同意，Tool 只是入口，不是运行模型

`spawn_subagent` 作为模型侧调用接口是合理的：模型仍然通过统一 Tool Schema 发起委派，不必感知底层调度实现。

但 Runtime 侧不能把它当成普通函数调用。真正可恢复的 Subagent 至少需要：

- 父 Run 与子 Run 的稳定 ID 和因果关系；
- 子 Run 独立状态机、Context、预算和权限；
- 父级权限只能向下收缩，不能由子级自行扩大；
- 启动、运行、完成、失败、取消和超时事件；
- 并发额度和资源租约；
- 父 Run 取消后的传播规则；
- 父进程退出后的孤儿检测与恢复；
- 结构化 Handoff 和 Artifact 引用；
- 重复 spawn 请求的幂等处理。

因此更准确的关系是：

```text
spawn_subagent Tool
  = 模型侧委派入口

Subagent Runtime
  = Child Run + Scheduler + Policy + Event + Result Handoff
```

如果只做同步、进程内、不可恢复的隔离子循环，可以不先建设完整 Durable Task；但这种实现只能称为轻量 Subagent，不能同时承诺后台运行、取消恢复和孤儿回收。

以当前目标架构看，真正的 Subagent 应排在 Run / Session / Event、Cancellation 和 Durable Task 之后。

### 8. 建议后的演进顺序

综合五点，建议把路线从“先扩能力、再补 Harness”调整为“先建立最小治理边界，再扩大执行规模”：

```text
v0.2 · Governed Tools
  Tool Contract 元数据
  Permission Outcome + 参数重写
  同步 ASK
  执行目标路由
  Tool / Policy Trace
  Skill
  MCP

v0.3 · Stateful Runtime
  Run / Session / RunEvent
  Event Stream
  Cancellation / Interrupt
  Approval Pause / Resume
  Checkpoint
  Context pruning / compaction
  Circuit breaker

v0.4 · Durable Composition
  Durable Task
  Background execution
  Child Run / Subagent
  失败与孤儿恢复
  Eval 闭环
```

这一顺序的核心依赖是：

- MCP 依赖基础 Tool Governance；
- 可恢复 Approval 依赖 Run / Event / Resume；
- Background Task 依赖 Durable execution；
- 真正 Subagent 依赖 Child Run 和父子状态传播；
- Eval 使用前面已经结构化的事件和决策，而不是另建日志体系。

### 9. 最终结论

这份 Review 对“当前真正缺口是运行闭环”的判断准确。五点中最重要的不是分别增加 Permission、ASK 或 Subagent 字段，而是重新排列系统依赖：

> 先让单个 Tool 调用可治理，再让单个 Run 可中断和恢复，最后才扩大到后台任务和 Subagent。

建议采纳以下三项核心调整：

1. 将“core 永远不改”改为“核心职责和不变量稳定，契约兼容演进”；
2. 将基础 Permission 前移到 MCP 之前，并作为外部工具进入执行面的门禁；
3. 将 Subagent 从“一个工具功能”重新定义为“通过 Tool 发起的 Child Run”。

ToolDecision 的扩展方向也应采纳，但需把互斥的授权结果与可叠加的参数重写、执行路由、审批请求拆开，避免再次形成混合维度的契约。
