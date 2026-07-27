# nanoagent 目标架构与演进蓝图

> 文档性质：基于面试官关注点整理出的 nanoagent 目标架构与后续演进蓝图。
>
> 本文不是当前实现说明，也不是对现有 `docs/DESIGN.md` 的替代。现有实现与契约仍以 `docs/DESIGN.md` 为准；本文描述下一阶段核心改进方向和长期目标架构。

## 一、面试官关注的点

- 定位与架构设计
  - nanoagent 的核心定位与实际工程价值
  - nanoagent 是否只是 ReAct demo
  - ReAct、Plan-and-Execute、Workflow 的边界
  - 核心循环与 Harness 的分层方式
  - Hook 与上下文干预的关系
  - 不同策略如何介入并影响控制流
- 上下文与状态管理
  - 上下文压缩的触发时机与压缩策略
  - 原始历史、任务状态与模型可见上下文的关系
  - Prompt Cache 命中率与上下文稳定性
  - 多轮任务中的目标、约束和决策链保持
- Memory 与知识体系
  - Working、Episodic、Semantic Memory 的边界
  - 如何向模型提供持续、准确的业务知识
- 能力组织与 Agent 组合
  - 不同 Agent 的工具、知识库、Memory 与策略组合
  - Skill、Tool、MCP 的能力组织方式
  - Subagent 与多 Agent 协作机制
- 检索与知识增强
  - 大规模代码仓库的上下文检索
  - RAG 的召回率、误报率与重排准确率
  - GraphRAG 的实体关系构建、更新、删除与质量评估
- AI Coding 与测试质量
  - AI Coding 在大仓库中的可维护性与变更质量
  - AI 生成测试中的业务断言质量
  - 覆盖率、测试通过与真实正确性的区别
- 安全、治理与人机协同
  - Human-in-the-loop、权限、审计与风险控制
  - Agent Runtime 与 AI 治理网关的关系
  - 企业内部 Agent 管理、团队记忆与技能沉淀
- 可靠性与评估体系
  - Trace、失败恢复与长期任务稳定性
  - Agent 能力如何形成可评估的质量闭环

这些关注点集中指向三个判断：能否把 Agent 抽象落到工程机制、能否形成质量闭环、能否支撑企业级治理和复杂任务。

本文可以分成三层看：

| 内容性质 | 定位 |
|---|---|
| Stable Core、能力与策略分离、Hook 注入、append-only 历史与模型 view | **现有设计基础** |
| Run / RunState / RunEvent、结构化 Hook Effect、Task State、Checkpoint、Tool Contract、Eval | **下一阶段核心改进方向** |
| Multi-agent、企业控制面、治理网关集成、完整 AI Coding、团队 Memory | **长期目标架构** |

## 二、nanoagent 应该是什么定位

### 目标定位

> **nanoagent 是一个以 Harness 为核心、基于事件溯源、由策略驱动的通用 Agent 运行时。**

它负责把模型的不确定推理过程，约束成一套：

- 可组合；
- 可控制；
- 可观测；
- 可恢复；
- 可评估；
- 可审计；

的任务执行过程。

它不应再以“30 行 ReAct 循环”作为主要价值。小核心只是实现手段，真正的产品价值应是：

> **用统一 Runtime 承载不同 Agent，通过 Tool、Skill、Memory、Context、Policy 和 Workflow 的组合，形成 AI Coding、知识 Agent、运维 Agent 和企业 Agent Team。**

现有设计中的 Stable Core、能力与策略分离、Hook 注入、append-only 日志与模型 view，构成了正确基础；目标形态应在此之上补齐任务状态、可靠执行、质量评估和企业治理。

### 总体分层

```text
应用层
CLI / IDE / Bot / Web / 企业业务系统

场景层
Coding Agent / Knowledge Agent / Ops Agent / Agent Team

编排层
Plan / Workflow / Subagent / Multi-agent Coordinator

Runtime 层
AgentLoop / Context Engine / Tool Executor / Policy Engine
Checkpoint / Recovery / Trace / Budget / Human Approval

能力层
LLM / Tool / Skill / MCP / Memory / Retrieval / Sandbox

基础设施层
模型网关 / RAG 服务 / 代码索引 / 向量库 / 图数据库
任务队列 / Event Store / OTel / Secret Manager
```

## 三、各要点应该如何设计

### 1. 核心执行模型

nanoagent 的核心不应只是一个 `while` 循环，而应由三个稳定对象组成。这种设计的目的，是把原本隐含在循环中的“任务状态、执行过程和历史记录”显式结构化，从而支持恢复、审计、调试和评估，而不是依赖模型上下文的偶然一致性。

#### Run

代表一次完整任务，是最外层的执行单元。可以理解为“用户发起的一次请求的生命周期容器”，用于统一管理任务的身份、配置和资源。

包含：

- `run_id`
- 用户与租户身份（用于权限与审计）
- Agent Profile 版本（确保行为可复现）
- 当前状态（运行中、暂停、完成、失败等）
- 成本与时间预算（用于控制资源消耗）
- Checkpoint（用于中断恢复）
- 最终产物（任务输出结果）

设计 Run 的意义在于：把一次任务从“对话过程”提升为“可管理的执行实体”，便于在系统层面进行调度、监控和治理。

#### RunState

代表当前可恢复状态，是任务在某一时刻的“结构化快照”。它不是简单的对话摘要，而是明确表达任务进展和决策的核心数据。

包含：

- 目标与验收标准（确保任务方向稳定）
- 用户约束（如权限、范围限制）
- 当前计划（Plan）
- 已完成任务
- 待执行任务
- 当前工作集（当前关注的信息）
- 关键决策（避免重复推理或丢失重要判断）
- 产物引用（代码、文件、结果等）
- 错误与重试状态

RunState 的作用是：让任务在中断后可以继续执行，而不是重新“猜测”之前发生了什么，同时也避免模型每轮都重新总结整个历史。

#### RunEvent

所有实际发生的动作写成不可变事件，是系统的“事实记录”。每一个行为都被记录下来，而不是只保留最终状态。

包括：

- 用户输入
- 模型请求与响应
- Plan 更新
- Tool 请求、授权、执行与结果
- Memory 读写
- 人工确认
- Context 压缩
- Checkpoint
- Error、Retry、Stop

这些事件按时间顺序追加，形成完整的执行轨迹。

设计 RunEvent 的核心意义是：把“过程”变成一等公民。相比只保存当前状态，事件日志可以支持：

- 回放任务执行过程（debug）
- 精确审计每一步行为（安全与合规）
- 分析模型决策路径（优化与评估）
- 在任意节点恢复执行（可靠性）

`RunState` 和模型上下文都由事件日志派生。也就是说，事件日志是唯一的事实来源，而状态和上下文只是它的不同视图。这样 Trace、恢复、审计、回放和 Eval 使用的是同一份数据，避免多套数据不一致的问题。

#### 三者关系（伪代码表达，含关系注释）

```python
class Run:
    def __init__(self, run_id, profile, budget):
        self.run_id = run_id
        self.profile = profile
        self.budget = budget
        self.status = "running"

        # RunEvent：所有行为的唯一事实来源（Source of Truth）
        # 不可变、只追加，用于恢复、审计、回放
        self.events = []

        # RunState：由 events 派生出的“当前任务状态视图”
        # 不直接修改，而是通过事件推导得到
        self.state = RunState()

    def append_event(self, event):
        # 1. 所有变化必须先写入事件（RunEvent）
        self.events.append(event)

        # 2. 再通过事件推导出最新状态（RunState）
        # => RunState 是 RunEvent 的函数结果
        self.state = derive_state(self.events)


class RunState:
    def __init__(self):
        # 当前任务目标（来自用户或计划）
        self.goal = None

        # 用户约束 / 系统约束
        self.constraints = []

        # 当前计划（Plan 是状态的一部分，而不是临时文本）
        self.plan = None

        # 任务拆解后的子任务列表
        self.tasks = []

        # 已确认的重要决策（用于避免上下文丢失）
        self.decisions = []

        # 产物引用（代码、文件、结果等）
        self.artifacts = []

        # 错误记录（用于恢复与重试）
        self.errors = []


class RunEvent:
    def __init__(self, type, payload):
        # 事件类型（model_call / tool_request / plan_updated 等）
        self.type = type

        # 事件内容（模型输出、工具参数、执行结果等）
        self.payload = payload

        # 时间戳（用于排序、回放、审计）
        self.timestamp = now()


def derive_state(events):
    # 从“事件日志”重建“当前状态”
    # => 体现 Event Sourcing：状态不是存储的，而是计算出来的
    state = RunState()

    for e in events:
        # 每个事件都会对状态产生影响
        apply_event(state, e)

    return state


def agent_loop(run: Run):
    # 主循环：驱动 Run 的执行
    while not should_stop(run):

        # Context 构建依赖：
        # - RunState（结构化当前状态）
        # - RunEvent（历史轨迹）
        # => 两者共同决定模型输入
        context = build_context(run.state, run.events)

        # Thought + Action（模型调用）
        model_output = call_llm(context)

        # 模型输出本身也是事件（记录推理轨迹）
        run.append_event(RunEvent("model_call", model_output))

        # Plan 更新（如果模型产生新计划）
        if has_plan_update(model_output):
            # Plan 不是直接写 state，而是通过事件进入系统
            run.append_event(
                RunEvent("plan_updated", extract_plan(model_output))
            )

        # Tool 调用（如果模型决定调用工具）
        if has_tool_call(model_output):
            tool_req = extract_tool_call(model_output)

            # 1. 记录“请求工具”的意图
            run.append_event(RunEvent("tool_request", tool_req))

            # 2. 执行工具（外部副作用）
            tool_result = execute_tool(tool_req)

            # 3. 记录执行结果（Observation）
            run.append_event(RunEvent("tool_execution", tool_result))

        # 注意：
        # Observation 并不是单独结构，
        # 而是通过 tool_execution / model_call 等事件体现

        # Checkpoint 基于 Run（包含 events + state）
        # => 可恢复整个执行过程
        checkpoint_if_needed(run)

    # Run 生命周期结束
    run.status = "finished"
```

#### 调用与执行位置说明

- 用户调用入口在 Run：创建 Run，并写入第一条 `user_input` 事件
- ReAct 执行发生在 `agent_loop` 中：每一轮对应一组 `model_call → tool_execution → event append`
- Plan 存储在 RunState 中：通过 `plan_updated` 事件持续演进
- 每一轮执行读取 RunState，并基于 RunEvent 追加新的执行轨迹
- Workflow（若存在）在 Run 外层或节点层调度，每个节点内部仍可运行 agent_loop

#### 关系总结

- Run：任务容器，负责生命周期与资源控制
- RunEvent：唯一事实来源（append-only）
- RunState：由事件派生的当前状态（可恢复）
- Context / Trace / Eval：全部基于 RunEvent 重建

ReAct 应作为默认的开放式执行器；确定性流程使用 Workflow；复杂任务可以在 Workflow 节点内部运行 ReAct。

---

### 2. Harness 与 Hook

Hook 应从简单回调升级为**有序 Middleware Pipeline（中间件流水线）**。所谓 Middleware Pipeline，可以理解为一条按顺序执行的处理链，每个中间件（Middleware）都会在请求或事件经过时进行处理、修改或决策，然后再传递给下一个中间件。这样可以把权限控制、日志记录、上下文修改、错误处理等逻辑拆分成多个独立模块，按顺序组合执行，使系统更清晰、可扩展、也更容易控制行为。

#### 生命周期

至少覆盖：

```text
on_run_start
before_turn
before_context_build
before_model
after_model
before_plan_update
before_tool_authorize
before_tool_execute
after_tool_execute
before_checkpoint
on_error
on_stop
```

#### Hook 返回结果

不能只有“执行副作用”或简单布尔值，应统一返回结构化 Effect。这样可以把 Hook 的结果从“隐式行为”提升为“显式决策”，让 Runtime 能够理解、组合和控制这些结果；同时避免不同 Hook 之间通过副作用相互影响，提升可预测性和可调试性；还能统一表达继续执行、修改上下文、拒绝操作、暂停等待人工确认等多种控制流分支，使策略、权限和执行逻辑解耦，并为审计、回放和 Eval 提供清晰的语义基础。

- 每个 Hook 的行为是显式的、可组合的，而不是隐式副作用，方便调试和审计
- 控制流可以被精细化管理（例如暂停、重试、拒绝），而不是只能继续或中断
- 不同策略可以在同一阶段协同工作，而不会互相覆盖或冲突
- Runtime 可以统一处理这些 Effect（例如统一做重试、审批、降级），降低复杂度
- Trace 和 Eval 可以基于 Effect 做结构化分析，而不是解析日志

这些 Effect 并不是每一步都一样返回，而是根据当前阶段和策略动态产生：

- `Continue`：默认继续执行
- `ModifyContext`：在构建上下文时调整输入
- `ModifyRequest`：在调用模型前修改请求
- `Deny`：阻止某个操作（如工具调用）
- `PauseForApproval`：需要人工确认
- `Retry`：触发重试逻辑
- `Fallback`：切换备用策略或模型
- `Stop`：终止整个 Run

也就是说，每一步返回的类型是统一的，但具体返回哪一种 Effect，是由当前 Hook 的逻辑和策略决定的，而不是固定不变的。

#### 执行规则

每个 Hook 声明：

- 优先级；
- 可读写字段；
- 是否可以改变控制流；
- 失败时 fail-open 还是 fail-close；
- 同步或异步；
- 超时；
- 是否必须审计。

Hook 是介入时机，Strategy 是算法，Policy 是决策规则，Capability 是执行能力。四者不能混在一起。

---

### 3. Context Engineering

上下文应拆成四层，而不是只有“完整历史”和“裁剪 view”。

#### 第一层：Event Log

完整、不可变、append-only，服务于：

- 恢复；
- 审计；
- Trace；
- Eval；
- 重新生成上下文。

#### 第二层：规范化任务状态（Canonical Task State）

这一层的核心作用是：**提供任务级的稳定语义锚点，避免模型在多轮中“忘记自己在做什么”。**

它不是简单的摘要，而是结构化、可持续更新的任务状态，用来解决：

- 多轮对话中目标漂移；
- 关键约束被覆盖或遗忘；
- 决策链断裂；
- Plan 丢失或被模型重写；
- 上下文压缩后信息不可恢复。

结构化保存：

- 当前目标；
- 验收标准；
- 用户硬约束；
- 已确认决策；
- 当前计划；
- 未解决问题；
- 关键实体和文件；
- 产物位置。

它的作用可以理解为：

> **在 Event Log 和 Model View 之间，提供一个“稳定、可控、可恢复”的任务语义层。**

与 Event Log 的区别：

- Event Log 是“发生了什么”（原始事实）；
- Task State 是“现在任务处于什么状态”（结构化理解）。

与 Model View 的区别：

- Model View 是“这一轮给模型看的内容”；
- Task State 是“跨轮保持一致的任务核心信息”。

因此，这一层是任务连续性的稳定锚点，不能依赖每轮重新摘要。

#### 第三层：Working Set

这一层的核心作用是：**控制当前轮真正参与推理的信息范围，避免上下文膨胀，同时保证决策所需信息完整。**

它解决的问题包括：

- 上下文过长导致成本和延迟爆炸；
- 无关历史干扰当前推理；
- 检索结果过多导致注意力分散；
- 工具输出过大影响模型判断；
- 当前任务焦点不清晰。

当前阶段真正需要的信息：

- 最近对话；
- 当前任务相关代码；
- 检索证据；
- 必要工具结果；
- 当前错误；
- 待处理文件。

可以理解为：

> **Working Set 是“这一轮真正需要思考的材料集合”，是动态裁剪后的工作上下文。**

与 Task State 的区别：

- Task State 是稳定的、长期存在的；
- Working Set 是短期的、随阶段变化的。

与 Model View 的关系：

- Working Set 是 Model View 的主要输入来源之一；
- Model View 会在 token 预算下进一步裁剪和组织 Working Set。

#### 第四层：Model View

根据 token 预算渲染出的最终请求。

模型 view 应按稳定区和动态区组织：

```text
稳定区：
System Prompt
Agent Profile
工具 Schema
Skill 摘要
任务目标
用户硬约束
已确认决策

动态区：
当前输入
当前计划步骤
局部检索结果
最近工具结果
错误信息
```

这样既降低目标丢失概率，也提高 Prompt Cache 命中率。

#### 四层关系总结

```text
Event Log：记录一切发生过的事实（完整历史）
Task State：抽取并维护任务当前状态（稳定语义）
Working Set：筛选当前轮需要的信息（动态工作集）
Model View：在预算内组织给模型看的输入（最终提示）
```

#### 压缩规则

压缩不应是“每轮让模型重写一遍摘要”，而应：

- 优先移除可重新获取的工具原文；
- 大结果转成 Artifact，只在上下文保留引用和摘要；
- 按字段增量更新 Task State；
- 保留关键决策的来源事件；
- 保证 tool call 与 tool result 成对；
- 压缩结果带版本、来源和覆盖范围；
- 支持从事件日志重新生成。

---

### 4. Memory（记忆）

#### Memory 与 Context 的关系

Memory 和上文的 Context 是两个不同层级的概念：

- **Context（上下文）**：是当前这一轮模型调用时实际提供给模型的输入，是一个“即时视图”，由 Task State、Working Set、检索结果等动态拼装而成。
- **Memory（记忆）**：是跨 Run、跨任务长期保存的信息，是“可被检索和复用的知识来源”。

两者的关系可以理解为：

```text
Memory（长期存储）
→ 通过 Retrieval / ContextProvider 被选取
→ 注入 Context（当前模型可见输入）
→ 模型产生决策
→ 再决定是否写回 Memory
```

因此：

- Context 是“当前可见”，受 token 限制；
- Memory 是“长期可用”，不直接进入模型；
- Context 是 Memory 的一个动态投影，而不是 Memory 本身；
- Memory 的质量直接影响 Context 的质量，但两者生命周期和结构不同。

目标形态应采用四类 Memory（记忆）。

#### Working Memory（工作记忆）

当前 Run 内的状态、上下文和临时产物。

说明：

- 与上文 Context 强相关；
- 实际上是 Context 的来源之一；
- 生命周期仅限当前任务；
- 不会自动进入长期 Memory。

#### Episodic Memory（情景记忆）

过去任务的过程经验：

- 做过什么；
- 使用了哪些工具；
- 哪些方案成功或失败；
- 最终结果；
- 用户反馈。

特点：

- 面向“经验复用”；
- 常用于类似任务的策略参考；
- 通常通过检索摘要形式进入 Context。

#### Semantic Memory（语义记忆）

稳定知识：

- 企业文档；
- 产品规则；
- 业务术语；
- API Schema；
- 代码知识；
- 历史问题。

特点：

- 面向“事实与知识”；
- 是 RAG 的主要来源；
- 更新频率较低，但需要版本与时间控制。

#### Procedural Memory（程序性记忆）

可复用的工作方法：

- Playbook；
- Skill；
- 操作流程；
- 测试规范；
- 代码审查规范；
- 企业员工经验沉淀。

特点：

- 面向“如何做”；
- 常以 Skill 或策略形式加载；
- 可以直接影响 Agent 行为，而不仅是提供信息。

#### Memory 写入机制

不能把所有对话自动写入长期记忆。应采用：

```text
模型提出候选记忆
→ Memory Policy 判断是否值得保存
→ 去重、归并、敏感信息检查
→ 写入指定作用域
→ 记录来源、置信度、版本和过期时间
```

作用域至少包括：

- 当前用户；
- 当前项目；
- 当前团队；
- 当前租户；
- 全局公共知识。

Memory 的读取结果必须携带 provenance，模型必须知道信息来自哪里、何时产生、是否已过期。

---

### 5. ReAct、Plan 与 Workflow（从 ReAct 演进到 Plan 的路径）

三者不应互相替代，而是逐步叠加能力。

你当前主循环是 ReAct，可以按“最小侵入”的方式逐步演进到 Plan，而不是一次性重写。

#### ReAct（当前阶段）

适合：

- 路径无法预先穷举；
- 需要边观察边决策；
- 工具结果会改变下一步；
- 探索型问题。

当前循环大致是：

```text
Thought → Action → Observation → Thought ...
```

这是一个“无显式任务结构”的执行模型。

#### 第一步：在 ReAct 上引入“隐式 Plan”（轻量升级）

目标：不改变主循环，只增加结构化任务意识。

做法：

- 在 Context 中增加一个 `current_plan` 字段（可以先是文本或简单列表）；
- 每轮让模型输出时，除了 Thought，还输出当前任务拆解；
- 在 Hook（如 after_model）中解析并更新 Plan；
- 不强制执行，只作为“辅助信息”。

示例：

```text
Thought: 我需要先找到相关文件，再修改逻辑
Plan:
1. 搜索相关代码
2. 阅读实现
3. 修改函数
4. 运行测试
Action: search_code
```

这一阶段的关键：

- Plan 只是“可见但不强制”的；
- 不改变 ReAct 控制流；
- 主要用于提升上下文稳定性和可解释性。

#### 第二步：把 Plan 变成 RunState 的结构化对象（核心升级）

目标：让 Plan 成为“状态”，而不是模型随时可能丢失的文本。

Plan 应是 RunState 中的一等对象：

```text
Plan
├── goal
├── constraints
├── tasks[]
│   ├── task_id
│   ├── objective
│   ├── dependencies
│   ├── allowed_tools
│   ├── expected_artifacts
│   ├── acceptance_criteria
│   └── status   (todo / doing / done / blocked)
└── revision
```

实现方式：

- 在 after_model Hook 中解析模型输出，生成结构化 Plan；
- 将 Plan 存入 RunState，而不是只存在上下文；
- 每次模型调用前，把“当前 Plan + 当前任务”注入 Model View；
- 当前执行的 Action 必须对应某个 task。

同时引入事件：

- `PlanCreated`
- `PlanUpdated`

每次修改都记录：

- 修改前版本；
- 修改后版本；
- 修改原因（模型解释或系统原因）。

#### 第三步：让 ReAct “围绕 Plan 执行”（控制流升级）

目标：从“自由探索”变成“有任务驱动的探索”。

核心变化：

- 每一轮不再是“随便想下一步”，而是：
  - 选择一个 task（通常是 status=todo 或 doing）；
  - 围绕该 task 进行 Thought / Action；
- Action 必须满足：
  - 在该 task 的 allowed_tools 内；
  - 服务于该 task 的 objective。

执行模型变为：

```text
Select Task → Thought → Action → Observation → Update Task Status
```

新增逻辑：

- 当 task 完成时，标记为 done；
- 如果失败，标记为 blocked，并记录原因；
- 如果发现 Plan 不合理，可以触发 Plan 更新（仍通过模型）。

#### 第四步：引入“Plan 驱动的停止条件”

目标：不再依赖“模型说完成了”，而是结构化判断。

停止条件变为：

- 所有 tasks.status == done；
- 或达到某个 acceptance_criteria；
- 或触发 Stop Policy（预算、错误次数等）。

这样可以避免：

- 模型提前结束；
- 或无限循环。

#### 第五步：在 Plan 上叠加 Workflow（长期）

Workflow 不应该简单理解为“最上层”或“最下层”，而是属于编排层的一部分，位于 Agent Runtime 之上、具体应用之下。

原因是：

- Workflow 负责定义“整体流程结构”和“执行顺序”，属于编排层；
- Plan 负责把目标拆解成任务，是策略层；
- ReAct 负责在不确定环境中逐步决策，是执行层。

当某些任务模式稳定后：

- 把固定流程抽成 Workflow；
- Workflow 的每个节点可以：
  - 执行一个 task；
  - 或运行一个完整 ReAct 子循环；
  - 或调用 Tool / 人工审批。

关系更准确的理解是“嵌套与约束”，而不是简单的上下层：

```text
Workflow（编排层：定义阶段、顺序、分支、审批等控制结构）
    ↓（约束执行范围）
Plan（策略层：在当前阶段内拆解任务、维护状态）
    ↓（驱动具体动作）
ReAct（执行层：逐步决策、调用工具、处理不确定性）
```

关键点：

- Workflow 不一定总在最外层：某些场景可以没有 Workflow，仅靠 Plan + ReAct；
- Plan 也可以在 Workflow 的某个节点内局部生成，而不是全局唯一；
- ReAct 始终是最底层执行机制，但它的运行范围可以被 Plan 和 Workflow 共同约束。

一句话总结：

> Workflow 决定“怎么走流程”，Plan 决定“要做哪些事”，ReAct 决定“每一步具体怎么做”。

#### 总结（演进路径）

```text
当前：
ReAct（无结构）

→ 第一步：
ReAct + 文本 Plan（辅助）

→ 第二步：
ReAct + 结构化 Plan（RunState）

→ 第三步：
Plan 驱动 ReAct（任务级控制流）

→ 第四步：
Plan 驱动停止与评估

→ 第五步：
Workflow + Plan + ReAct（完整体系）
```

一句话总结：

> 不要“从 ReAct 切换到 Plan”，而是让 ReAct 逐步被 Plan 约束和驱动，最终变成 Plan 的执行引擎。

#### Workflow

适合：

- 流程固定；
- 需要强制执行顺序；
- 存在审批步骤；
- 涉及高风险操作；
- 需要稳定回归。

Workflow 应作为独立编排层，每个节点可以是：

- 确定性函数；
- Tool；
- LLM 调用；
- 完整 Agent Run；
- 人工审批；
- Subagent。

默认策略是：

> 开放问题使用 ReAct；高风险、可重复的流程使用 Workflow；Plan 负责连接两者。

---

### 6. Tool、Skill 与 MCP

#### Tool

Tool 是最小执行能力，必须声明：

- 输入与输出 Schema；
- 是否只读；
- 副作用等级；
- 访问的资源范围；
- 超时；
- 重试策略；
- 幂等键；
- 补偿操作；
- Sandbox 配置；
- 是否需要人工确认；
- 并发限制。

副作用等级可以分为：

```text
READ_ONLY
REVERSIBLE_WRITE
IRREVERSIBLE_WRITE
EXTERNAL_SIDE_EFFECT
```

权限和执行策略依据副作用等级决定，而不是只根据工具名判断。

#### Skill

Skill 应是一个完整能力包：

```text
Skill
├── manifest
├── instructions
├── tools
├── context providers
├── memory scope
├── policies
├── examples
└── eval cases
```

采用渐进式加载：

```text
加载 Skill 简介
→ Agent 判断需要
→ 加载 Manifest
→ 需要执行时加载完整指令和工具
```

#### MCP

MCP 是外部工具来源，不应成为内部核心抽象。

所有 MCP Tool 应先归一成 nanoagent 内部 Tool Contract，再经过：

- 权限校验；
- 参数校验；
- 超时；
- 审计；
- Sandbox；
- 结果清洗。

---

### 7. Subagent 与多 Agent

Subagent 不应只是“再启动一个 Agent”，而应是一个受控任务委派机制。

从工程视角看，委派可以类比为“创建一个受控的子执行单元”，类似子进程或子任务，但并不等同于操作系统层面的子进程。它更接近于：

- 一个独立的执行上下文（类似子进程的地址空间隔离）；
- 一个可调度、可中断、可回收的任务单元；
- 一个拥有受限资源与权限的运行实例。

是否真的映射为子进程，取决于具体实现（线程、协程、任务队列、远程调用等都可以），但在抽象层面，它的本质是：

> 在当前 Run 内创建一个隔离的子 Run，用于完成一个明确子目标，并通过结构化结果回传。

#### Task Assignment

主 Agent 委派时必须提供：

- 明确目标；
- 输入 Artifact；
- 可用工具；
- Memory 作用域；
- 预算；
- 验收标准；
- 返回格式。

#### 隔离

每个 Subagent 具有：

- 独立 Context；
- 独立预算；
- 独立工具权限；
- 独立 Trace；
- 受限 Memory；
- 可取消的生命周期。

主 Agent 不接收完整对话，只接收：

- 结构化结果；
- 证据引用；
- 产物；
- 未解决问题；
- 风险说明。

#### Multi-agent

多 Agent 不应采用无约束的群聊模式，而应采用：

```text
Coordinator（协调器）
→ Task Graph（任务图）
→ Specialist Agents（专业 Agent）
→ Typed Handoff（类型化交接）
→ Artifact Merge（产物合并）
→ Verification（验证）
```

共享的是 Artifact 和结构化状态，不是所有 Agent 的完整上下文。

只有在任务能并行、需要专业能力隔离或需要独立上下文时才拆 Agent；否则单 Agent + Tool 更稳定。

---

### 8. RAG 与 GraphRAG

RAG 不应只作为一个普通搜索 Tool，也不应硬编码进核心循环。应抽象为 `ContextProvider`，同时支持：

- Agent 显式调用；
- Context Engine 根据任务自动召回。

#### Retrieval Pipeline

```text
Query Understanding
→ Retrieval Plan
→ 多路召回
→ 过滤与权限裁剪
→ 融合去重
→ Rerank
→ Evidence Budget
→ 注入 Model View
```

多路召回应覆盖：

- 关键词与符号匹配；
- 向量语义召回；
- 关系图召回；
- 元数据过滤；
- 时间与版本过滤。

返回对象应统一为 Evidence：

```text
Evidence
├── content
├── source_id
├── source_type
├── retrieval_channel
├── score
├── version
├── timestamp
├── permission_scope
└── graph_path
```

#### GraphRAG

GraphRAG 应负责关系证据，而不是替代文本召回。

离线侧：

- Schema / entity type 约束；
- 实体与关系抽取；
- 归一与消歧；
- 来源绑定；
- 增量更新；
- 图膨胀控制。

在线侧：

- 实体与关系 Query 分解；
- 入口实体召回；
- 有界子图扩展；
- 回表获取原文；
- 图关系与文本证据联合排序。

更新删除采用：

> 原始抽取作为 Source of Truth，图索引作为可重建派生视图；删除或变更后按剩余来源重建，并通过重试和对账保证最终一致。

这是已有 GraphRAG 项目中最值得迁移到 nanoagent Retrieval 层的设计。

---

### 9. AI Coding 场景

AI Coding 应作为 nanoagent 的第一个标准场景包，而不是把代码逻辑写进通用 Runtime。

#### 代码知识底座

不能只做普通文档 Embedding，应建立：

- 文件和目录索引；
- AST；
- Symbol Table；
- 定义与引用；
- Import Graph；
- Call Graph；
- 继承关系；
- API Schema；
- 配置项；
- 测试与实现映射；
- Git 变更历史；
- 历史 Bug 与 Review 记录。

召回采用：

```text
路径召回
+ 符号召回
+ 关键词召回
+ 语义召回
+ 依赖关系召回
+ Git 历史召回
```

索引按 Git Diff 和内容 Hash 增量更新，不能频繁全仓重建。

#### 代码修改流程

```text
1. 明确需求与验收标准
2. 构建 Repo Map
3. 影响面分析
4. 生成修改计划
5. 高风险变更人工确认
6. 在独立 Worktree / Sandbox 修改
7. 小批量生成 Patch
8. 静态检查与测试
9. 语义 Review
10. 输出 Diff、证据与回滚点
```

#### 变更约束

每次任务定义：

- 允许修改的文件；
- 禁止修改的模块；
- 最大变更行数；
- API 兼容要求；
- 数据迁移要求；
- 是否允许改依赖；
- 是否允许联网；
- 必须执行的测试；
- 必须人工确认的动作。

AI Coding 的质量来自“受约束的变更闭环”，而不是模型一次性生成大量代码。

---

### 10. 测试质量保障

测试生成应采用“先设计、再生成、再验证”的 Workflow。

#### 为什么要设计 Test Plan

直接让模型生成测试，往往会出现以下问题：

- 测试只覆盖表面行为，缺乏业务语义；
- 断言弱（例如只判断 200 或非空）；
- 忽略关键状态变化和副作用；
- 无法系统性覆盖异常路径；
- 测试与需求脱节，难以评估是否真正验证了正确性。

引入 Test Plan 的核心目的，是**把“测试目标”从代码生成中前置出来，使测试具备明确的验证意图和可评估标准：**

- 将业务需求结构化为可验证的测试设计；
- 强制模型在生成代码前理解“要验证什么”，而不是“怎么写测试”；
- 提高测试的可解释性和可审查性；
- 为后续自动评估（Eval）提供稳定依据；
- 支持测试复用、回归和质量对比。

本质上，Test Plan 是测试质量的“约束层”，而不是生成层。

#### Test Plan

每个测试必须先明确：

- 业务场景；
- 前置状态；
- 输入数据；
- 调用链路；
- 关键业务断言；
- 异常分支；
- 状态变化；
- 外部副作用；
- 清理逻辑。

#### Test Generation

根据 Test Plan 生成：

- 单元测试；
- 集成测试；
- Contract Test；
- 回归测试；
- Golden Case；
- Property-based Test。

#### 质量门禁（怎么做）

自动识别弱测试：

- 只断言 HTTP 200；
- 只断言非空；
- 没有业务字段断言；
- 没有验证状态变化；
- Mock 掉了真正需要验证的链路；
- 测试无论实现正确与否都能通过。

具体实施步骤：

1. 在测试生成或提交阶段，运行静态规则扫描，自动标记上述弱测试模式；
2. 对被标记的测试，要求补充业务断言或拒绝合入；
3. 在 CI 流程中加入自动校验步骤，确保所有测试满足最基本的断言质量要求。

验证手段包括：

- Mutation Testing：通过自动对代码进行小幅修改（例如改变条件判断、返回值等），观察现有测试是否能够捕捉到这些变化，从而评估测试的敏感度和有效性；
- 故意修改实现，确认测试能失败：人为引入错误或不符合预期的实现，验证测试是否会失败，以确保测试不是“无论如何都通过”的弱测试；
- Contract Schema 校验：根据接口或数据结构的约定（Schema），检查输入输出是否符合预期格式和约束，确保系统之间的契约没有被破坏；
- Golden Response：使用预先定义好的标准输出（黄金结果）作为对照，比较当前输出是否一致，用于验证关键路径或核心逻辑的正确性；
- 状态前后对比：在执行操作前后对系统状态进行对比（例如内存数据、文件内容、业务对象状态等），确认是否发生了预期的变化；
- 数据库与外部副作用检查：验证操作是否正确地影响了数据库或外部系统（如消息队列、第三方服务等），确保不仅返回结果正确，实际副作用也符合预期。

落地方式：

1. 在 CI 中集成 Mutation Testing 工具，定期运行并输出覆盖报告；
2. 对关键路径引入 Golden Case，对比输出是否稳定；
3. 在测试执行后自动检查数据库或外部系统状态变化；
4. 将上述验证结果作为合入门禁条件之一，未通过则阻断发布。

覆盖率只作为“哪些代码被执行”的指标，不能作为正确性的核心指标。

---

### 11. Eval 质量闭环

Eval 必须成为 Runtime 的原生能力，而不是项目完成后的附属脚本。

这一部分的核心是在建立一个“可验证、可回归、可量化”的质量体系，把 Agent 的行为从“看起来合理”变成“可以被系统性评估”。它的目标不是单次判断好坏，而是让每一次改动（模型、Prompt、Tool、Policy、Memory）都能通过统一标准进行对比和回归，从而形成持续优化的闭环。

#### 三层 Eval（含义与区分）

这三层 Eval 分别对应 Agent 系统的三个不同层面：底层执行机制、过程决策质量和最终任务结果。它们关注的问题不同，组合起来才能完整评估一个 Agent 是否“既能跑、又跑得对、还能交付正确结果”。

##### Runtime Eval（运行时机制层）

这一层关注的是系统本身是否按预期工作，属于“基础设施正确性”。

验证：

- Hook 顺序是否正确执行；
- Tool 调度是否符合设计；
- 权限策略是否正确阻断非法操作；
- Checkpoint 是否按时持久化；
- 重试机制是否生效；
- Context 压缩是否触发且不破坏结构；
- Stop 条件是否正确终止任务。

可以理解为：**系统有没有按规则运行**，不关心模型“想得对不对”。

##### Trajectory Eval（执行过程层）

这一层关注 Agent 在执行过程中的决策质量，属于“推理路径正确性”。

验证执行过程：

- 是否选择了合适的工具；
- 工具参数是否合理；
- 是否出现无意义或重复调用；
- 是否偏离既定计划；
- 是否遗漏关键证据或上下文；
- 在失败后是否采取了合理的恢复策略。

可以理解为：**Agent 是不是在“正确地做事”**，即过程是否合理、有效。

##### Scenario Eval（任务结果层）

这一层关注最终交付结果，属于“业务正确性”。

验证最终任务：

- 任务是否真正完成；
- 产物是否符合预期；
- 测试是否通过；
- 是否引入新的问题或回归；
- 是否满足用户提出的约束条件。

可以理解为：**最终结果是不是对的、有没有价值**。

总结：

- Runtime Eval：系统有没有正常运行；
- Trajectory Eval：过程是否合理；
- Scenario Eval：结果是否正确。

三层从底到上逐层递进，缺一不可。

#### 指标

- Task Success Rate（任务成功率）
- Tool Call Accuracy（工具调用准确率）
- Policy Violation Rate（策略违规率）
- Context Retention Rate（上下文保持率）
- Retrieval Recall / Precision（检索召回率 / 精确率）
- Recovery Success Rate（恢复成功率）
- Human Intervention Rate（人工干预率）
- Latency（延迟）
- Token / Cost（Token 消耗 / 成本）
- Patch Acceptance Rate（补丁接受率）
- Regression Rate（回归率）

评价优先级应是：

```text
可执行结果
> 确定性规则
> Golden Case
> LLM Judge
> 人工抽检
```

不能主要依赖“让另一个大模型判断这个大模型做得好不好”。

---

### 12. 权限、安全与治理

#### 身份链路

每次 Run、模型调用和工具调用都必须携带：

- `tenant_id`
- `user_id`
- `agent_id`
- `run_id`
- `policy_version`
- `data_classification`

#### 权限系统

采用 deny-first：

- 未明确授权则拒绝；
- 权限按工具、资源和操作类型判断；
- 读取权限与修改权限分开；
- Agent 不能自行扩大权限；
- 高风险操作需要 Human Approval。

#### Sandbox

代码和工具执行环境应支持：

- 文件系统隔离；
- 工作目录白名单；
- 网络出口控制；
- Secret 隔离；
- CPU / 内存 / 时间限制；
- 子进程回收；
- Artifact 导出；
- 环境销毁。

#### Prompt Injection 防护

外部文档、网页和代码注释全部视为不可信数据：

- 数据与系统指令分层；
- 检索内容不能修改权限策略；
- Tool 参数由 Schema 验证；
- 敏感操作不能只依据检索内容触发；
- 工具结果进入上下文前做清洗和标记。

#### 与 AI 治理网关的关系

网关负责：

- 模型鉴权；
- 虚拟 Key；
- 限流限额；
- 模型路由；
- Prompt / Response 安全；
- 调用审计。

nanoagent Runtime 负责：

- Agent 内部权限；
- Tool 调用治理；
- Context 与 Memory 治理；
- Plan 和执行审计；
- Sandbox；
- Checkpoint 与恢复。

两者通过统一的身份、Trace 和 Policy Metadata 贯通，而不是重复实现。

---

### 13. 可观测性与可靠执行

#### Trace

Trace 树应覆盖：

```text
Run
├── Turn
│   ├── Context Build
│   ├── Memory Retrieve
│   ├── LLM Call
│   ├── Plan Update
│   ├── Tool Authorization
│   ├── Tool Execution
│   └── Checkpoint
└── Final Evaluation
```

每个 Span 记录：

- 输入输出摘要；
- Token；
- 延迟；
- 成本；
- Model；
- Tool；
- Retry；
- Policy 决策；
- Evidence ID；
- Error。

#### Checkpoint 与恢复

以下节点后持久化：

- Plan 更新；
- 模型响应；
- 有副作用的 Tool 执行；
- 人工审批；
- Context 压缩；
- Subagent 完成。

恢复时从最后一个 Checkpoint 继续，而不是重新执行整个任务。

#### Tool 可靠性

- 只对幂等操作自动重试；
- 非幂等操作使用 idempotency key；
- 可逆操作提供 compensation；
- 不确定是否执行成功时先查询实际状态；
- 长任务使用持久化队列、租约和心跳；
- 超时任务进入待恢复状态；
- 重复事件通过 event_id 去重。

---

### 14. 企业级控制面与运行面

#### Control Plane

管理：

- Agent Profile；
- Prompt 与模型配置；
- Tool / Skill Registry；
- Memory Scope；
- Policy；
- Eval Suite；
- 版本；
- 灰度发布；
- 租户配额；
- 审计查询。

#### Data Plane

执行：

- Run；
- Context 构建；
- 模型调用；
- Tool 调度；
- Sandbox；
- Checkpoint；
- Trace；
- Artifact 管理。

Agent Profile 应是可版本化配置：

```text
AgentProfile
├── model_policy
├── system_prompt
├── skills
├── tools
├── context_policy
├── memory_policy
├── permission_policy
├── stop_policy
├── sandbox_profile
├── eval_suite
└── version
```

不同 Agent 的差异主要体现为 Agent Profile 的不同，而不是复制或修改一套新的核心代码。

## 四、最终应形成的能力标签

nanoagent 最终不应被描述成：

> 一个很小的 ReAct Agent 框架。

而应被描述成：

> 一个面向真实任务的 Agent Runtime：以事件日志和任务状态保证上下文连续性，以 Harness 和 Policy 约束模型与工具行为，以 Memory、Retrieval、Skill 和 Workflow 组合不同 Agent，以 Checkpoint、Trace、Sandbox 和 Eval 保证过程可恢复、结果可验证，并能与企业模型网关和治理体系集成。

最核心的四个标签是：

1. **Harness-first**：工程约束不是后补功能，而是 Runtime 主体。
2. **Event-sourced**：执行、恢复、审计和 Eval 基于同一事件事实源。
3. **Policy-driven**：上下文、权限、成本、工具和停止条件均由可配置策略控制。
4. **Eval-native**：每个 Skill、Agent Profile 和版本都有可回归的质量依据。

---

## 五、Architecture Review

### 1. 总体判断

整体方向成立，而且比现有设计更能回答面试官真正关心的问题：nanoagent 不只是能运行 ReAct，而是尝试把不确定的模型行为纳入可管理的执行系统。

但需要明确：

> 这份内容适合作为目标架构（North Star），还不能直接作为下一版本的施工蓝图。

它目前混合了架构原则、核心重构、能力清单、场景方案和企业平台设想。主要问题不是内容不足，而是尚未从完整目标中收敛出“下一步必须验证什么”。

最有价值、应当保留为主干的判断包括：

1. **Run / RunState / RunEvent**：这是从“对话循环”升级为“任务运行时”的关键，直接支撑恢复、审计、Trace 和 Eval。
2. **Event Log → Task State → Working Set → Model View**：四层分别回答事实、当前状态、当前工作材料和模型输入，解决现有 `messages + view()` 只能处理裁剪、不能稳定表达任务状态的问题。
3. **Harness-first 与 Policy-driven**：权限、预算、审批、重试和上下文干预成为执行语义，而不是外围辅助。
4. **Eval 与 Runtime 使用同一份执行事实**：避免 Trace、恢复、审计和评估各自维护一套数据。
5. **Subagent 传递结构化结果和 Artifact，而不是共享完整上下文**：能够控制上下文污染、权限外溢和协作成本。

### 2. 必须正面处理的架构断点

这份蓝图不是在现有设计上简单增加几层，而是在重新定义 Core。

现有 `DESIGN.md` 的核心承诺是：

- `Context.messages` 是事实日志；
- 8 个 Hook 固定；
- 只有 `before_tool` 返回控制结果；
- Harness 可以拿掉，循环退化成纯 ReAct；
- 后续引入 Harness 时 `core/` 不变。

新蓝图则要求：

- `RunEvent` 成为唯一事实源；
- `RunState` 成为正式运行状态；
- Hook 升级为能够暂停、重试、降级和修改请求的 Effect Pipeline；
- Checkpoint、恢复和 Policy 成为 Runtime 主体；
- Harness 不再是可选外围，而是核心产品价值。

这两套定义不能同时成立。

如果目标定位确定为 Harness-first、Event-sourced Runtime，应明确承认一次架构升级：

> v0.1 的 Stable Core 是最小执行内核验证；vNext 重新定义 Runtime Core。稳定的应当是语义约束，而不是现有 dataclass、8 个 Hook 和 30 行循环永远不变。

否则，为了维护“core 一行不改”的旧承诺，会把 Run、Checkpoint、Effect 等硬塞到循环外面，最终只能观察执行，无法可靠控制暂停、重试、审批和恢复。

### 3. 需要校准的具体定义

#### 3.1 Event Sourcing 不等于每次从头计算状态

伪代码中的：

```python
self.state = derive_state(self.events)
```

每次追加都全量重放，执行成本会随事件数量持续增加。更准确的实现是：

- 正常执行：事件追加后，由 reducer 增量更新物化状态；
- 恢复和验证：从最近快照开始重放后续事件；
- Event Log 是事实源，但 RunState 可以持久化为带事件偏移量的 projection。

Checkpoint 更适合表示：

```text
state snapshot
+ event sequence
+ execution cursor
+ artifact references
+ inflight side-effect status
```

而不是简单保存“完整 events + state”。

#### 3.2 事件必须覆盖外部副作用的不确定状态

当前的 `tool_request → tool_execution` 不足以表达“工具已经执行成功，但结果回传前进程崩溃”的状态。至少需要区分：

```text
requested
authorized
started
succeeded / failed / unknown
```

恢复时对 `unknown` 先查询实际结果，不能直接重试。否则即使有 Checkpoint，也可能重复产生副作用。

#### 3.3 记录可观察执行轨迹，不依赖内部推理轨迹

系统可以记录模型请求、响应、Tool Call、Plan 变更、Effect、证据引用和最终决策。但“记录推理轨迹、分析模型决策路径”应改为“记录可观察执行轨迹”，不能把不可获得或不稳定的内部思维过程作为恢复和审计前提。

#### 3.4 Hook Effect 不能成为所有阶段共用的万能返回值

统一 Effect 的方向合理，但不同阶段允许的结果不同：

- Context 阶段：修改 Working Set 或 Model View；
- Model 阶段：修改请求、重试、Fallback；
- Authorization 阶段：Allow、Deny、Pause；
- Error 阶段：Retry、Recover、Stop；
- Stop 阶段：只观察或补充结果，不能重新修改历史。

更稳妥的方式是“统一 Effect 基类 + 阶段限定的 Effect 联合类型”。同时必须定义冲突归并规则：

- `Stop` 是否压过 `Retry`；
- 多个 `ModifyContext` 按什么顺序合并；
- `Deny` 和 `PauseForApproval` 同时出现时谁生效；
- 哪些字段禁止多个 Middleware 同时写。

否则只是把隐式副作用换成了结构化但仍不确定的冲突。

#### 3.5 RunState 与 Canonical Task State 应统一

两部分当前实质重复。更清晰的关系是：

> Canonical Task State 是 RunState 中负责表达任务语义的主体，而不是另一个并列状态系统。

RunState 还可以包含执行游标、预算、重试和当前审批等运行字段；Canonical Task State 保存目标、约束、计划、决策和产物。

#### 3.6 Memory 四分类混合了不同维度

当前分类不完全同层：

- Working 按生命周期划分；
- Episodic、Semantic 按内容性质划分；
- Procedural 更接近 Skill、Playbook 或行为配置。

实现设计应拆成三个正交维度：

- 生命周期：Run-local / Long-term；
- 内容类型：Episode / Fact / Procedure；
- 作用域：User / Project / Team / Tenant / Global。

Procedural 内容可以存储在 Memory 中，但真正影响行为时，应经过版本化 Skill 或 Policy 加载，不能让普通检索内容直接改变执行规则。

#### 3.7 Tool 副作用等级并不互斥

`READ_ONLY / REVERSIBLE_WRITE / IRREVERSIBLE_WRITE / EXTERNAL_SIDE_EFFECT` 中，外部副作用可能同时是只读、可逆或不可逆。更适合拆成独立字段：

```text
access_mode: read / write
reversibility: reversible / irreversible / unknown
boundary: local / external
approval_level
idempotency
```

权限策略再综合判断，而不是依赖单一枚举。

#### 3.8 ReAct 不是所有执行路径的必经底座

“Workflow → Plan → ReAct”在开放式节点中成立，但确定性 Workflow 节点可能直接调用函数、Tool 或人工审批，完全不需要 ReAct。更准确的表述是：

> Workflow 定义控制结构；Plan 表达待完成任务；ReAct 是处理不确定任务的一种节点执行器，而不是所有执行路径的必经底座。

#### 3.9 Prompt Cache 只能作为待验证的设计目标

稳定前缀能为缓存创造条件，但实际命中率取决于模型供应商的缓存规则、序列化稳定性和动态字段位置。没有实测数据前，只能说“优化缓存条件”，不能直接判断命中率提升幅度。

#### 3.10 GraphRAG 迁移价值目前不能判断

本文没有包含已有 GraphRAG 项目的实现、质量指标和运行结果。现有描述在架构上合理，但是否值得优先迁移、能否复用，依据不足，目前不能判断。

### 4. 建议收敛出的下一阶段

下一阶段不宜同时做 Multi-agent、GraphRAG、AI Coding、企业控制面和完整 Memory。建议只验证一个闭环：

> 单 Agent 在存在外部工具副作用的任务中，能否基于事件和结构化状态实现可控制、可恢复、可评估的执行。

范围收敛为：

1. `Run + typed RunEvent + EventStore`
2. 增量 `RunState reducer + snapshot`
3. `Task State + Working Set + Model View`
4. Artifact 引用与一种可验证的压缩策略
5. 阶段限定的 Effect，先覆盖权限、模型调用和错误恢复
6. Tool Contract 的权限、副作用和幂等元数据
7. 最小 Checkpoint / Resume
8. 基于相同事件的 Trace 和少量 Runtime / Scenario Eval

验收标准应当可证伪：

- 中断恢复后，不重复执行已完成的副作用；
- 能从事件还原 Tool 的请求、授权、执行和结果；
- 大工具结果转为 Artifact 后，目标和约束仍然保留；
- 相同事件和版本能够重建相同 RunState；
- 权限拒绝、审批和重试能够被结构化审计；
- 修改 Policy、Context Strategy 或模型后，可以运行同一批 Case 做回归比较。

Multi-agent、GraphRAG、团队 Memory、Control Plane 和完整 AI Coding 可以保留在目标架构中，但不进入这一阶段。面试官关注这些问题，证明项目需要能够解释边界和演进路径，不足以证明 nanoagent 应立即自行实现全部平台能力。

### 5. Review 结论

这份蓝图的核心判断是对的：nanoagent 的长期价值不应停留在 ReAct demo，而应转向可控制、可恢复、可评估的任务 Runtime。

真正需要调整的不是继续补充能力，而是：

1. 明确它会重构现有 Core，而不是假设完全兼容；
2. 把重复和不同层级的概念重新归位；
3. 从完整目标架构中切出一个能验证核心闭环的下一阶段；
4. 把未经项目证据验证的企业级能力保留为远期边界，不提前形成硬承诺。

本文因此应保持为目标架构；后续再从中独立提炼范围严格、带接口和验收标准的 vNext Runtime 实现设计。
