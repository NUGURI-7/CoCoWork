# CoCoWork 架构战略指导

> 本文档是 CoCoWork Agent 体系的地基性约定。它定义「不变的承重结构」，不涉及实现细节与排期。任何功能迭代都应在本文档的边界内发生；若某需求要求改动第 1–9 节，才需重新审视地基。

---

## 1. 基调

> **deepagents 是一颗无状态的执行核（本质是一个函数：编图 → invoke）。CoCoWork 做的，是它外面一层薄壳 + 塞进它内部的一组 middleware。**

- **薄壳**（框架外）：跑前拼装参数、跑后收拢结果。
- **middleware**（框架内）：每次 LLM 调用时生效的横切逻辑——这是工程主体。

我们不是「自造 agent 引擎」，而是「在 deepagents 公开的扩展点上，把一个 harness 组装成一个产品」。

---

## 2. 三条不可推翻的立场

1. **Harness 是外部依赖。** deepagents 只升级、不 fork、不改其内部。CoCoWork 代码永远在它外侧，仅通过公开扩展点（`create_agent` 参数 / `AgentMiddleware` 协议 / backend）与之交互。
2. **Workspace 逻辑 = 可插拔横切层。** 所有 workspace 特有逻辑以 middleware 或外层装配存在，绝不散入业务代码。新增能力 = 加一个 middleware 或改一条装配规则，不动主干。
3. **Agent 每请求装配，非常驻对象。** 招募、换模型、改资源，都是「改装配参数」，不是「改架构」。

---

## 3. 角色与命名

| 架构层（代码 / 文档） | 职责 |
|---|---|
| **Supervisor**（全程统一用此词，对外/对用户/讲故事一律 Supervisor） | 主入口。接收请求、拆解、派活、整合；主入口起、主入口收。**精确指代时加限定词**——见下消歧。 |
| **NPC** | 干活的叶子 agent。 |

> 不引入「管家 / Butler」别名。`Supervisor` 在工程圈有辨识度（supervisor pattern），统一一个词省心；产品文案里也直接用 Supervisor。

### 3.1 Supervisor 内部结构 + 命名消歧

> 「Supervisor」一词可能指「整个外层图系统」或「内部那个 create_agent 节点」。**靠限定词消歧，不靠换名字。**

```
Supervisor 系统 / Supervisor 图  ← 整个外层图（永远存在，默认结构）
└─ Supervisor brain / Supervisor loop  ← 那个 create_agent + SubAgentMiddleware 节点
                                       （派活、调度、轮子都在这）
└─ [其他节点按需填充：forced_search / audit / fan-out 等]
```

| 精确指代 | 用法 |
|---|---|
| **Supervisor 系统 / Supervisor 图** | 整个外层结构。对外、对用户、讲故事时用。 |
| **Supervisor brain / Supervisor loop** | 那个 `create_agent` 节点。代码里精确指代时用。 |
| **Supervisor**（裸用） | 上下文清楚时简称即可。 |

- **brain 节点**装自主决策 + 派活 + 全部 deepagents 轮子（task 工具、subagent 委派、context 隔离）。"派活"永远是 brain 节点的行为。
- **外层图的其他节点**只放：确定性强制步骤、命名节点级审计、确定性 fan-out 等"必须固定"的事；**不许在外层图里手写派活/调度逻辑**（那是 brain 节点的活，写在外层 = 丢轮子）。
- 第 4 节「Supervisor 能调哪些 NPC 跑前锁死」指的是 **brain 节点的 subagents 参数**——外层图其他节点跟这个无关。

**默认结构：外层图永远在、brain 永远是它的一个节点。** 「按需」的不是图壳本身，而是图壳里**放哪些节点**——见第 7.1 节。

---

## 4. 三个接入面（CoCoWork 代码只能落在这三处）

| 接入面 | 职责 | 轻重 |
|---|---|---|
| **跑前（外层）** | 拼本次执行的参数：Supervisor 带哪些 NPC、选哪个 backend | 薄 |
| **跑中（middleware）** | 每次 LLM 调用时生效：可见性、记忆注入、模型分级、记账 | **重 —— 主体** |
| **跑后（外层）** | 收拢结果：持久化、产出并回、总记账 | 薄 |

**源码硬约束：** Supervisor 能调哪些 NPC，在「跑前构造」时即锁死，middleware 无法在运行中改变。因此「本 workspace 招了谁」必须是外层职责。

---

## 5. 两个永恒锚点

- **`workspace_id`** —— 资源、记忆、成员、记账的归属维度。
- **`agent_role`** —— 一次调用「我是谁」（supervisor / 某 NPC / 临时专家），决定看什么、用什么、写哪层记忆。

只要这两个标识稳定，其下所有字段可自由增删而不动结构。

---

## 6. 状态归属（早定，后期不挪）

| 状态 | 归属 | 约束 |
|---|---|---|
| 会话执行态（checkpoint） | harness checkpointer | 框架管，不碰 |
| 跨会话记忆 | Store（按 workspace/user 分 namespace） | 作用域语义由 CoCoWork 定 |
| 业务配置（workspace / NPC / 资源 / 花名册） | CoCoWork 业务库 | 完全自有 |

**铁律：业务态绝不进 checkpointer；会话态绝不进业务库。**

---

## 7. Agent 模型

**模板（Template）：** 一个**产出 `CompiledStateGraph` 的配方**——可以是 `create_agent` 配方（参数挑一组 middleware），也可以是手写 `StateGraph`。模板 workspace 无关，进程启动时编好、全平台共享、复用。

**形态自由：**
- **需要确定性固定流程**（如 PPT NPC 必须 大纲→排版→渲染→审查）→ `StateGraph` 手写图
- **不需要固定流程**（如研究员、文案，开放任务由 LLM 自主决定）→ `create_agent` 体系

> 两种 NPC 可混在同一 workspace。判据是「这个 NPC 是否真需要固定步骤」，不是「区分度大不大」——专业差异化的载体是 prompt + tools + knowledge + model + middleware 组合，不是图拓扑。

**NPC：** = 模板 + 挂载的资源（知识库 / tool / skill）。用户在 agent 模块基于内置模板挂资源来创建。

**两条铁规：**
1. **NPC 永远 2 层、不可派生。** NPC 不挂 `SubAgentMiddleware`，物理上没有派活能力。**只有 Supervisor 派活。** 不留开关。
2. **两类 NPC，两条干净的产生路径：**
   - **招募的 NPC**（在 workspace 花名册里）→ 请求装配 Supervisor 时，按花名册接成 **subagent**（复用 deepagents 的 task 工具与 context 隔离）。招募 / 解雇 = 改花名册数据（配置态 CRUD，运行前）。
   - **临时 NPC**（花名册外、运行中才需要）→ 给 Supervisor 一个 **`spawn_from_template` 工具**：运行中实例化模板图、执行、折回结果（当 tool，不当 subagent，绕开构造锁）。

**嵌套注意（源码）：** 父 agent 调子 agent 只转发 state、不自动转发 typed context。NPC 所需的 workspace 上下文须放进会被转发的 state，不可依赖 context 自动下传。

### 7.1 外层图 = 默认结构；按需的是节点填充

> 这是结构原则，不是排期。**外层薄图永远存在，brain 永远是它的一个节点；"按需"指的是图内除 brain 之外要不要加 forced_search / audit / fan-out 等节点，不是图壳本身的存在与否。**

- **默认结构（永远套）**：每次请求都跑同一张外层图——`StateGraph` 包 brain 节点（`create_agent + SubAgentMiddleware`）。**没有运行时分支**：不存在"这次请求要不要套图"的代码判断。
  - 为什么默认就套：state 穿层 + 流式穿层的集成税早晚要付；一次付清、结构从此统一，**好过将来回头重构加图**。
  - 起步阶段：外层图就只有 brain 一个节点，结构最简。功能到了再往这张已存在的图里加节点，不是新建图。
- **按需的是节点填充**：forced_search / audit / fan-out 这些节点**功能到了才往这张已存在的图里加**，不是一开始就堆空节点占位。
- **触发条件失效就摘掉节点**：节点不是地位象征，没人用就摘。但**图壳一直在**。
- **GraphNPC（手写图 NPC）同理判据**：默认全 `create_agent` 配方，只有 PPT 这类"必须固定步骤"的 NPC 才升级为手写图。

**结构口诀：图壳默认有，节点按需填。**

---

## 8. 功能落点（总账）

- **原生白嫖（deepagents）：** Supervisor 调度、NPC per-role 配置、全能力 NPC（deep agent 当 subagent）。
- **写 middleware（跑中）：** 可见性、作用域记忆、三层资源合并、模型分级、记账。
- **写外层（框架外）：** workspace 概念、@ 直连分发、招募/解雇 CRUD、临时 NPC 装配。

### 8.1 强制步骤的落点（Perplexity 式固定时机）

> 形如「每次回答前必须先检索」「每次结束前必须自检」这类**固定时机的强制步骤**，落点优先级：

1. **默认：做成 brain 上的 middleware（`before_model` / `wrap_model_call`）。** 横切性强、不破图结构、跟可见性/记账等其他 middleware 同栈编排。
2. **例外升级为外层图节点：** 只有当业务上**真**需要「命名节点级审计」（合规可见）或「确定性排序」（图拓扑保证）时，才把该步骤提升为外层图的命名节点。
3. **判据**：能用 middleware 表达 → 永远用 middleware；只有图拓扑能给的强保证才值得动外层图。

---

## 9. 唯一的核心硬骨头

> **多 Agent 共享对话的「视图隔离 + 回写一致性」** —— 谁看到哪段上下文、谁的产出如何干净地并回共享对话。

- **机制锚点：Supervisor↔NPC 的派活边界。** 派出去前裁可见性、收回来后折产出，**与 NPC 内部形态（手写图 / agent loop）解耦**。这是 NPC 形态能彻底自由的根本原因——核心横切不依赖钻进 NPC 内部。
- **机制定死：** 一个按规则过滤上下文、并按规则回写产出的 middleware（`WorkspaceContext`），且保证 prompt 前缀稳定不破 cache。
- **规则待定：** 「哪些该看 / 不该看」是产品策略，后续逐步填，不阻塞机制开工。
- 这是整个体系唯一需要深设计、且注定多版迭代的地方，演进预算几乎全押于此。

### 9.1 派活的两种实现（按路径选，不是全局选）

派活边界有两种落地形态，**默认全 A，某条路径真需要确定性并发才升 B**：

| | A. brain 并行 task 调用（**默认**） | B. 外层图 `Send` 确定性 fan-out |
|---|---|---|
| **决策方** | brain loop 的 LLM 临场决定并发派给谁 | 外层图节点写死拓扑、分发节点可审计 |
| **保留 deepagents 轮子** | ✓ 全保留（task 工具、context 隔离、折回都走原生） | ✗ 需要自己重写那一小段折回逻辑 |
| **审计粒度** | 工具调用级 | 命名节点级 |
| **何时用** | 绝大多数场景 | 业务上必须确定性并发 + 节点级审计的特殊路径 |

**关键：A/B 按路径选，不是全局选。** 一个 workspace 里大多数对话走 A，某条特殊业务流（如「文案+PPT 必须并行启动、合流审计」）那条路径升级到 B，其他不受影响。

---

## 10. 战略一致性护栏

护栏不是技术禁令，是保护第 1–2 节基调不被无声破坏。

1. **派活/调度永远在 brain loop 内，禁止「图替换 loop」。** brain loop 必须用 `create_agent` 体系（`create_agent` 或 `create_deep_agent`，按需挑 middleware），派活靠 `SubAgentMiddleware`。**禁的是「图替换 loop」**——把派活/调度逻辑自己写进手画的 `StateGraph` 节点里，绕开 deepagents 调度内核重造一遍。**允许「图包 loop」**——外层薄 `StateGraph` 只放确定性/强制/审计节点，brain loop 作为其中一个节点，派活仍在 brain。判别口诀：**「图包 loop ✓，图替换 loop ✗」**。
2. **NPC 形态自由**（手写图 / `create_agent` 均可，按是否需要固定流程决定）。核心横切锚在 Supervisor↔NPC 派活边界，NPC 内部形态不影响地基。
3. **LangChain 跨大版本（→ 2.x）属于第 11 节「才回地基」的极少数情况**——1.x 内部小升级随意，跨 2.x 必须先回来重审扩展点（`AgentMiddleware` 协议 / `ModelRequest` / `Runtime` / `Store` / `Command`）是否仍稳定。

---

## 11. 迭代判据

任何新需求，只问一句：

> **它能落进「改数据 / 改装配规则 / 加一个 middleware」吗？**

- 能 → 日常迭代，地基不动。
- 不能（极少）→ 才回到第 1–7 节重审地基。

---

## 附录 A：源码依据 + LangGraph 适配

> 基于 deepagents 主线源码（撰写时尚未 pin 入 `backend/pyproject.toml`，待引入时回填具体版本号）+ LangChain 1.x。

### A.1 地基断言的源码出处

| 地基断言 | 源码证据 | 结论 |
|---|---|---|
| deepagents 是「无状态执行核（函数）」 | `create_deep_agent(...) -> CompiledStateGraph`（graph.py:99），返回 `create_agent(...).with_config(...)`（graph.py:295） | ✓ 返回的就是一张编译好的图，每请求 invoke |
| 三个接入面之「跑前构造」收 LangGraph 持久化原语 | 签名直接收 `checkpointer: Checkpointer`、`store: BaseStore`、`cache: BaseCache`（graph.py:92-98） | ✓ 状态三分里的 checkpointer/Store 是原生入口 |
| 横切逻辑走 `AgentMiddleware` 协议 | 所有 middleware 基于 `langchain.agents.middleware.types.AgentMiddleware`，内部用 `langgraph.runtime.Runtime` / `langgraph.types.Command` | ✓ 自研 middleware 就继承这个基类 |
| subagent 列表构造期锁死 | `subagent_graphs` 在 `_build_task_tool` 一次建好（subagents.py:391） | ✓ 招募必须跑前定 |
| NPC 不挂 `SubAgentMiddleware` 就没派活能力 | subagent 默认 middleware 栈不含 `SubAgentMiddleware`（graph.py:220） | ✓ 2 层锁成立 |
| 临时 NPC 走 spawn 工具可绕构造锁 | `task` 工具本质是「invoke 子图 + 折回」（subagents.py:445），`spawn_from_template` 工具同形状 | ✓ |
| 嵌套只转发 state、不转发 context | `subagent.invoke(subagent_state)` 不带 `context=`（subagents.py:445） | ✓ NPC 上下文须放进 state |
| 「图包 loop / 图包图」可成立 | `CompiledStateGraph` 可作为节点直接传给父图 `add_node(...)`；父图把它当不透明节点 invoke。LangGraph 子图组合是一等公民 | ✓ 外层薄图包 brain loop 是原生支持的拓扑 |

### A.2 与 LangGraph 的适配性

**结论：不是「适配」，是「本来就是」。** 适配性满分，无阻抗失配。

1. **deepagents 的产物就是 LangGraph 图。** `create_deep_agent` 返回 `CompiledStateGraph`；`create_agent` 把 middleware 编译进一张 LangGraph 图（middleware 不是独立 runtime，是跑在编出来的图里）。所以你拿到的东西天生就是 LangGraph 一等公民——能当节点塞进更大的 `StateGraph`、能嵌套当 subagent、能上 checkpointer/store/cache、能流式、能 interrupt，全部原生。

2. **「外层薄壳」和 LangGraph 无缝。** workspace 数据通过 `runtime.context` / `get_config()` 注入（middleware 就这么读的，见 `memory.py:60`、`summarization.py:72`）；持久化用 `PostgresSaver` / `PostgresStore`——这俩就是 LangGraph 自己的后端，直接插进 `create_agent` 的 `checkpointer` / `store` 参数，零适配。

3. **自研 middleware 扩 `AgentState`**（LangGraph state schema），用 `PrivateStateAttr` 控暴露——跟官方 middleware 同一套机制。workspace 状态就活在 LangGraph state 里，该有 reducer 有 reducer、该私有私有。

### A.3 适配性唯一的「但是」

| 选择 | 后果 |
|---|---|
| brain loop = `create_agent` 体系（**采用**，对应第 10 节护栏 1） | workspace middleware 在 brain loop 和每个 NPC 节点内统一生效。无缝。 |
| 外层薄图包 brain loop（**默认结构**，见 §7.1：图壳永远在、节点按需填） | middleware 在 brain 节点内仍自动生效；外层图其他节点上不自动跑，但那些节点本就只放确定性/审计内容，**不需要 agent middleware**——所以不算缺口。 |
| 用手写 `StateGraph` 替换 brain loop、自写派活/调度（**禁用，对应「图替换 loop」**） | LangChain middleware 只在 agent 节点内跑，自定义调度节点上不自动跑（社区 issue 在催 `wrap_agent_call` 的点）。跨节点横切（如全局记账）得在节点边界自己接，且 deepagents 调度内核（task / context 隔离 / 嵌套）全部丢失。 |

地基选「外层图默认套 + brain 节点 + 节点按需填充」，所以稳。

### A.4 版本面

`deepagents` 上游 pin：`langchain>=1.2.11,<2.0.0`、`langchain-core>=1.2.18,<2.0.0`。LangGraph 由 LangChain 透传。扩展点（`AgentMiddleware` / `ModelRequest` / LangGraph `Runtime` / `Store` / `Command`）在 1.x 线稳定，`<2.0.0` 的 pin 替你挡住了大版本漂移。**只要留在 LangChain 1.x，接口不会塌。**

### A.5 已知约束

**并行调用 + checkpointer 命名空间冲突**

- 约束：per-thread 带 checkpointer 的子图被并行调用同一个会出 checkpoint 命名空间冲突。
- **但 deepagents 默认路径绕开它**——task 工具 `subagent.invoke(fresh_state)` 不带 checkpointer（subagents.py:445），子 agent 构造也没传 checkpointer（subagents.py:660），所以**默认并行派活（§9.1 的 A 形态）安全**。
- **触发条件**：只有当主动给 NPC 配 per-thread checkpointer（为 NPC 内部 HITL / 跨刷新持久化）时才会触发。
- **防呆**：将来给 NPC 加 checkpointer 必须先确认调用形态（串行 / 不同 thread_id / 不并行同一 NPC），否则会踩雷。

---

## 维护规则

- 本文档随源码确认结论演进，更新附录 A 时同步标注 deepagents 版本。
- 第 1–9 节属承重墙，修改必须走第 11 节「回地基重审」流程。
- 第 10 节护栏可随源码事实增删（每条护栏都应有第 1–9 节里的立场出处）。
