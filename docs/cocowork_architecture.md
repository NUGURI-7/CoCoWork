---
title: CoCoWork 架构决策:外层 StateGraph + butler 持 NPC sub-agent
date: 2026-06-05
doc-type: decision
tags: [cocowork, architecture, butler, npc, sub-agent, workspace-context, langchain-1.0]
summary: CoCoWork 采用"外层薄 StateGraph 持 workspace 数据 + butler 作 create_agent 节点 + NPC 作 butler 的 sub-agent"架构。三种候选架构对比后选定此方案,理由是数据所有权干净、产品语义对齐、单 agent 阶段可起步。
---

# CoCoWork 架构决策:外层 StateGraph + butler 持 NPC sub-agent

## TL;DR

1. **选定架构**:外层薄 `StateGraph` 持 workspace 数据,butler 作为 `create_agent` 节点位于其中,NPC 作为 butler 的 sub-agent(被 butler 通过工具调用触发)。
2. **拒绝方案 A(butler 内部持 workspace)**:虽然单 agent 阶段最简单,但 workspace 数据深埋在 butler state 里,sub-agent 难对称访问。
3. **拒绝方案 B(完全扁平 StateGraph,butler 和 NPC 平级节点)**:NPC 数量动态,每加一类 NPC 就要加图节点;butler 的"调度"角色被拍平成图路由,产品语义对不上。
4. **选定方案 C 的核心理由**:workspace 数据放最外层 → 跨 agent 对称读写;butler 仍持调度权 → 产品定位是管家而非平级;通过 middleware 注入 workspace 上下文 → 干净分层。
5. **架构演进路径**:单 agent 阶段直接 `create_agent` 加 middleware 即可,workspace 上下文用空 schema 占位;workspace 阶段把外层 StateGraph 加上,middleware 内部填真实逻辑,butler 主体不动。
6. **关键工程实践**:state schema 模块共享、字段名一致、middleware 实例不存请求级状态、外层和内层用同一份 schema 定义。

详见下文;某点想单独深入,沿 `#tag:` 拎话题。

---

## 三种候选架构 #tag:three-candidates

**讨论过的三种架构,各有清晰的形态和取舍。**

### 方案 A:butler 内部持 workspace

```
StateGraph (薄薄一层壳)
  └─ butler = create_agent
       state: { workspace_id, npcs, messages }
       tools: [delegate_to_npc, search_knowledge, ...]
```

butler 是 workspace 的化身,workspace 数据深埋在 butler state 里。NPC 通过 butler 的工具调用触发,作为 sub-agent 运行。

### 方案 B:完全扁平的 StateGraph

```
StateGraph (workspace 本体)
  state: { workspace_id, npcs, messages }
  ├─ butler = create_agent   ← 只决定下一步去哪
  ├─ npc_writer = create_agent
  └─ npc_researcher = create_agent
```

butler 和所有 NPC 都是 StateGraph 平级节点,butler 只输出 routing 决策,实际跳转由条件边完成。

### 方案 C:外层 StateGraph + butler 持 sub-agent(选定)

```
WorkspaceStateGraph
  state: { workspace_id, npcs, shared_memory, messages }
  └─ butler = create_agent
        tools: [delegate_to_npc, ...]
        middleware: [WorkspaceContextMiddleware()]
        sub-agents: NPCs(通过工具或 SubAgentMiddleware)
```

外层薄图持 workspace 数据,butler 通过 middleware 从外层 state 读 workspace 上下文,NPC 仍是 butler 的下属。

## 为什么不选方案 A #tag:reject-a

**最大问题:workspace 数据深埋在 butler state 里,sub-agent 难对称访问。**

- butler 调 sub-agent 时,要把 workspace 数据**显式作为参数传过去**——sub-agent 不在 butler 的 state 范围内,默认拿不到
- 多个 sub-agent 想读同一份 `shared_memory`,要每次都从 butler 转一手
- workspace 级别的横切关注点(可见性裁剪、权限校验)放 butler 内部 middleware,sub-agent 跑的时候这些 middleware 不生效

**单 agent 阶段它最简单**,但 workspace 阶段需要返工。

## 为什么不选方案 B #tag:reject-b

**两个本质问题:NPC 数量动态、butler 调度角色被拍平。**

**问题 1:NPC 数量动态扩展时图节点要跟着改。**
- 每加一类 NPC 就要 `add_node`、加条件边逻辑
- StateGraph 的拓扑是静态编译的,运行时动态加 NPC 很别扭

**问题 2:butler 的"调度"角色不对了。**
- CoCoWork 产品定位 butler 是**管家**,NPC 是它的下属——这是层级关系
- 方案 B 把 butler 和 NPC 拍成平级,butler 退化成"只输出 routing"的弱角色
- "管家调度下属"这个动作本来该是 butler 的 tool_call,变成了 StateGraph 的边

代码结构跟产品语义对齐,后期改起来不别扭。方案 B 这一点上对不齐。

## 方案 C 的核心理由 #tag:choose-c

**三件事同时满足:数据所有权干净、产品语义对齐、单 agent 阶段可起步。**

| 维度 | 方案 C 的做法 |
|---|---|
| workspace 数据所有权 | 最外层 StateGraph 持有,所有节点对称访问 |
| butler 的产品角色 | 保留管家定位,NPC 仍是它的工具/sub-agent |
| 横切关注点(可见性、权限) | 通过 WorkspaceContextMiddleware 注入,跟着 butler 走 |
| NPC 动态扩展 | NPC 是 butler 工具表里的一项,加 NPC 不动图拓扑 |
| 单 agent 阶段起步 | 外层 StateGraph 可以先省略,后期再加,butler 主体不变 |

**关键机制**:外层 state 跟 butler 内层 state 通过**同名字段**自动对接(见 `04_state_schema.md`)——外层有 `workspace_id`,butler 的 middleware 也声明 `workspace_id`,数据自动流入。

## 架构演进路径 #tag:evolution-path

**两个阶段,主干代码不动,只填空。**

**阶段 1:单 agent 起步**

```python
class WorkspaceContextMiddleware(AgentMiddleware):
    state_schema = WorkspaceState   # 占位 schema
    
    @wrap_model_call
    def inject(self, request, handler):
        # 单 agent 阶段:直接透传,什么都不做
        return handler(request)

butler = create_agent(
    model=...,
    tools=[...],   # 暂时没有 delegate_to_npc
    middleware=[WorkspaceContextMiddleware()],
)
```

外层 StateGraph 可以**完全不要**,直接 `butler.ainvoke(...)` 跑。

**阶段 2:接入 workspace + NPC**

```python
# middleware 内部填真实逻辑
class WorkspaceContextMiddleware(AgentMiddleware):
    state_schema = WorkspaceState
    
    @wrap_model_call
    def inject(self, request, handler):
        wid = request.state["workspace_id"]
        # 注入 workspace 上下文到 prompt、按可见性裁剪工具...
        return handler(request)

# 加外层 StateGraph
workspace_graph = (
    StateGraph(WorkspaceState)
    .add_node("butler", butler)
    .add_edge(START, "butler")
    .compile()
)
```

**butler 的 `create_agent(...)` 调用本身一个字不用改**——这就是"留口子"的物理意义。

## NPC 作为 sub-agent 的实现选择 #tag:npc-as-subagent

**两种实现路径,各有适用场景。**

| 实现 | 形态 | 适合 |
|---|---|---|
| **NPC 作为 butler 的工具** | `tools=[delegate_to_writer, delegate_to_researcher]`,工具内部 `npc_writer.ainvoke(...)` | NPC 数量少、调用模式简单 |
| **NPC 作为 SubAgentMiddleware 管理的 sub-agent** | 用 deepagents 的 `SubAgentMiddleware` 把 NPC 注册成命名 sub-agent | NPC 数量多、需要更结构化的委派/汇报 |

**早期建议先走工具路径**——简单直接,跑通 demo 再考虑要不要换 SubAgentMiddleware。

**NPC 本身的实现**也有选择:

- 简单 NPC → `create_agent(...)`
- 长任务 NPC(研究、代码生成) → `create_deep_agent(...)`
- 流程非 agent loop 的 NPC(确定性 pipeline) → 自己写 `StateGraph`

## WorkspaceContextMiddleware 的职责 #tag:workspace-middleware-job

**这个 middleware 是架构 C 里的核心,负责"workspace 数据 → butler 行为"的桥梁。**

预期承担的事:

- 把 workspace 当前状态注入 system prompt(workspace 名、当前 NPC 列表、shared_memory 摘要)
- 按可见性规则裁剪 butler 能看到的工具/NPC(不是所有 NPC 在所有 workspace 都可见)
- 把 butler 的 tool_call 记账到 workspace 级别的统计(token 用量、调用次数)
- 工作空间级别的人工审批策略(某些 workspace 调某些工具要审批)

**不该承担的事**:

- 具体业务持久化(写业务表)→ 放 service 层
- NPC 自身的逻辑 → NPC 自己的 middleware
- 用户级别认证 → FastAPI 路由层

## 关键工程实践 #tag:engineering-practices

**确保架构干净的几个硬规则。**

| 规则 | 原因 |
|---|---|
| state schema 放共享模块,外层和 middleware 从同一份导入 | 字段名天然一致,跨层对接不出错 |
| middleware 实例不存请求级状态(不用 `self.xxx`) | middleware 跨请求共享,会污染 |
| 请求级数据走 `state` 或 `runtime.context` | 这是 LangChain 1.0 设计的官方通道 |
| workspace 数据字段命名一致(都叫 `workspace_id`,不混用 `wid`/`ws_id`) | 跨层流转的前提是同名 |
| 单 agent 阶段也挂 WorkspaceContextMiddleware(留空 schema) | "留口子",workspace 阶段直接填,主干不动 |

## 架构演进的非破坏性 #tag:non-breaking-evolution

**这套架构最大的优点是"加东西不破坏现有东西"。**

| 演进事件 | 影响范围 |
|---|---|
| 加一类 NPC | butler 工具表加一项,NPC 自己定义一个 create_agent。**不动外层图、不动 middleware。** |
| 加 workspace 字段(比如 `current_topic`) | 共享 schema 加一个字段,middleware 按需读。**不动 butler 和 NPC 主体。** |
| 加新的横切关注点(比如审计日志) | 加一个新 middleware,挂上去。**不动现有 middleware。** |
| 接入新模型 provider | 改 `model=` 参数。**不动其他任何东西。** |

每一种演进都是**局部修改**,这是分层架构的核心收益。

## 当前未决问题 #tag:open-questions

**还没彻底想清楚的事,继续讨论时优先解决。**

- NPC 作为 butler 工具 vs SubAgentMiddleware 的具体选择标准
- workspace 级别的 checkpointer 怎么落地(每个 workspace 独立 thread_id?)
- 多用户共享同一 workspace 时的 state 隔离策略
- shared_memory 的具体形态(messages 之外的字段如何持久化、跨 thread 共享)

这些都属于"接入 checkpointer 阶段"才必须解决的问题,当前架构决策不阻塞它们。

---

## 外部参考

- [Custom workflow 文档](https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow) — create_agent 嵌入 StateGraph 的官方示例,跟方案 C 形态一致
- [Middleware Overview](https://docs.langchain.com/oss/python/langchain/middleware/overview) — middleware 在 create_agent 内的位置和工作方式
- [deepagents GitHub](https://github.com/langchain-ai/deepagents) — SubAgentMiddleware 的设计,理解 NPC 作为 sub-agent 的另一种实现
