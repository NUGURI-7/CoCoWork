# CoCoWork Agent 模块设计 v1

> 本文档是 agent 模块的产品 + 架构定型，作为后续切片实施的依据。
> 编写时间：2026-05-26（基于多轮讨论沉淀）

---

## 0. 一句话定位

CoCoWork agent 模块以 **"工作空间 + 单 agent 双入口"** 为核心：
- **Agent 模块** 提供单 agent 配置 + 直接对话（轻量入口，类 ChatGPT 体验）
- **工作空间** 提供多 agent 协作环境（管家调度 + 多成员接力 + 共享资源）
- **没有"调试 / 发布"二元状态**：配置改动立即生效，对话即真实使用
- **一切皆可注入**：Agent 是装备槽，工作空间是注入引擎，扩展性是核心设计目标

---

## 1. 范式定型

### 1.1 不做的事（v1 明确砍掉）

- ❌ **不做"发布 / 快照"动作** —— 没有草稿 vs 线上的二元状态
- ❌ **不做对外公网 URL / 嵌入脚本 / SDK** —— 不是给陌生人当客服的 SaaS
- ❌ **不让用户改 graph 拓扑** —— 行为是 LangGraph 内置模板，用户选模板不写代码
- ❌ **不让用户创建模板** —— 模板由平台运营，用户只创建 Agent
- ❌ **v1 不做多模态 / WebSocket** —— 暂缓，后续按需补
- ❌ **v1 不做沉淀（长期记忆）** —— 数据结构预留，能力 v2 再补

### 1.2 跟同类产品的对照

| | MaxKB / Dify | Claude Code / Cursor / Codex | CoCoWork |
|---|---|---|---|
| 定位 | 配置好再发布给客户用 | 单人开发工具 | 个人 / 团队的 agent 协作环境 |
| 核心动作 | 配置 → 调试 → 发布 | 对话 → 任务 | 装备 → 招募 → 协作 |
| 多 agent | 工作流编排（节点画布） | 后台 subagent 自动调用，对用户透明 | **同一会话内多 agent 接力 + @ 直选** |
| 资源管理 | 应用维度 | 项目维度 | **三层挂载（自带 / 空间共享 / 实例覆盖） + 注入引擎** |
| 调试 vs 使用 | 二元割裂 | 不分 | **单 agent 模式有轻调试 + 工作空间模式直接用** |

### 1.3 narrative（README 顶部用）

> **CoCoWork** 不是配置好再发布的 agent 平台（MaxKB / Dify），也不是单人对话工具（Claude / Cursor）。
>
> CoCoWork 是给个人 / 团队**装备一组 agent 协作工作**的环境：
> - 单 agent 直接用（**Agent 模块**），从平台模板挑一个，挂上 prompt / 模型 / knowledge / tool，开聊
> - 多 agent 协作（**工作空间**），把毛坯模板或调好的 Agent 招进同一会话，管家自动调度 + @ 直选并存
> - 资源（knowledge / tool）三层挂载（模板自带 / 空间共享 / 实例覆盖），取并集去重
> - **一切皆可注入**：工作空间是注入引擎，给招进来的 agent 注入资源 / 上下文 / 规则
> - 用得越久越合身（v2）—— 用户画像、工作空间世界观、实例工作记忆，全部从日常使用中自然沉淀

---

## 2. IA（信息架构）

### 2.1 Sidebar 布局

```
- 主页
- 工作空间       ← 多 agent 协作入口
- Agents         ← 用户 Agent 管理 + 单 agent 对话（含模板池展示）
- 知识库
- 工具
- 模型
- 设置
```

### 2.2 两个入口的职责对照

| | Agents（`/agents`） | 工作空间（`/workspaces`） |
|---|---|---|
| 列表页 | 三带式（Header + 模板池横向带 + 我的 Agent 卡片网格） | 工作空间卡片网格 |
| 详情页 | 左配置 + 右对话（两栏） | 通讯录 sidebar + 主对话 + 产出物面板 |
| 适合场景 | 单 agent 任务、临时聊、装备模板成 Agent | 长期项目、多 agent 协作、复杂任务 |
| 沉淀可读范围（v2） | 仅 L1（用户画像） | L1 + L2 + L3 |

---

## 3. 核心实体（重要：v1 关键概念）

### 3.1 三层实体关系

```
模板 (Template) ← 平台内置，不可编辑，纯行为骨架
└── 只有 LangGraph 的代码编排（拓扑/状态机）
└── ❌ 没有 prompt
└── ❌ 没有模型绑定
└── ❌ 没有任何 knowledge / tool / MCP 挂载
└── 是个"空壳骨架"，装备槽

   ↓ 用户/工作空间/管家给它"装备"

Agent (用户在 /agents 创建的资产)
└── 用户选某个模板 → 用户挂 prompt + 模型 + knowledge + tool
└── 模型必填（不配模型没法调 LLM）
└── prompt 非必填（无 prompt = 裸 LLM 也能聊）
└── /agents 列表页展示用户的 Agent

Agent 实例 (工作空间内的"招募成员")
└── 来源 1: 直接招毛坯模板 → 工作空间注入资源（prompt 前缀 / 共享 knowledge 等）
└── 来源 2: 招用户已建好的 Agent → 在已有挂载基础上再注入空间级资源
└── 实例属于空间，跟原模板/原 Agent 脱钩（之后改源不影响实例）
└── 在空间内可继续个性化（实例覆盖层挂载）

Subagent (管家临时 new)
└── 基于某模板 + 父 agent 部分上下文 + 即时装备
└── 用完即销毁，不进通讯录
```

### 3.2 模板（Template）

- **完全由平台运营**，用户不能创建、不能编辑、不能删除
- 每个模板规定一种"行为骨架"（LangGraph graph 拓扑，比如 `single` / `supervisor` / `pipeline` / `react` 等）
- 模板**自身没有 prompt、模型、资源挂载**——它是个空壳
- 模板池在 Agents 列表页第二带**只读展示**，没有独立 sidebar 入口

### 3.3 Agent（用户的资产）

- 用户在 `/agents` 基于某个模板创建
- 创建后用户可编辑：

| 字段 | 用户可改 | 必填 |
|---|---|---|
| 名字 / 头像 / 描述 | ✅ | 名字必填 |
| 模型 + 调用参数 | ✅ | **模型必填** |
| Prompt | ✅ | 非必填 |
| 关联 knowledge | ✅ | 非必填 |
| 关联 tool / MCP | ✅ | 非必填 |
| 行为模板（graph 拓扑） | ❌ | 创建时选定，不可改 |

### 3.4 Agent 实例（工作空间内成员）

- 由模板或 Agent **复制**而来，跟源**脱钩**（源后续改动不影响已有实例）
- 工作空间会**注入额外配置**（详见 §7 资源挂载 + §10 数据结构原则）
- 实例可在空间内继续个性化（实例覆盖层）

---

## 4. Agent 模块（单 agent 入口）

### 4.1 列表页布局（三带式）

```
┌─ ① Header ─────────────────────────────────┐
│  Agents          [+ 创建 Agent]            │
├─ ② 模板池（只读横向卡片条） ────────────────┤
│  研究员  写手  校对  调查员  ...（→ 滚动）  │
├─ ③ 我的 Agent（卡片网格） ──────────────────┤
│  ┌────┐  ┌────┐  ┌────┐                   │
│  │ A  │  │ B  │  │ C  │                   │
│  └────┘  └────┘  └────┘                   │
└────────────────────────────────────────────┘
```

- **第二带模板池**：横向滚动，每个模板是只读卡片，点击 = 「基于此模板创建 Agent」打开创建流程
- **第三带我的 Agent**：用户已创建的 Agent 卡片网格，点击进详情
- **空态**：模板池正常展示 + 第三带换成引导文案「从一个模板开始创建你的第一个 Agent」
- **创建按钮**：点击弹窗选模板（也可从第二带卡片直接点）

### 4.2 详情页布局（左配 + 右聊）

**左配置栏字段顺序**：

1. 基础 —— 名字 / 头像 / 描述
2. 行为模板 —— 只显示，不可改（创建时定）
3. 模型 —— 下拉选已建 chat 模型（**必填**）
4. 调用参数（可折叠） —— temperature / top_p / max_tokens
5. Prompt —— 大文本框（非必填）
6. 知识库 —— 多选关联
7. 工具 / MCP —— 多选关联

**保存即生效**：用户改了配置 → 下一句对话用新配置 → **无"发布"按钮**

### 4.3 右对话栏两种模式

| 模式 | 持久化 | 用途 |
|---|---|---|
| **正常对话** | ✅ 历史落库，可回顾 | 真实使用，像 ChatGPT 网页 |
| **调试对话** | ❌ 临时沙盒，关闭即清 | 试一下新配置 |

切换方式：右栏顶部 tab，默认正常对话。

### 4.4 沉淀（v2）

Agent 模块对话时，agent 只能读 **L1 用户画像**，拿不到任何工作空间相关记忆。Agent 自身无跨空间状态。

---

## 5. 工作空间（多 agent 入口）

### 5.1 详情页布局

```
┌─────────────────────────────────────────────────┐
│ Header: 空间名 + 设置入口                          │
├──────────────┬──────────────────────┬───────────┤
│ 通讯录       │ 主对话区               │ 产出物面板 │
│ sidebar      │                       │ （可折叠）│
│ - 管家       │ ┌────────────────────┐│           │
│ - Agent 1    │ │ user / agent 气泡   ││           │
│ - Agent 2    │ │ 含 agent 名标注     ││           │
│ - ...        │ └────────────────────┘│           │
│ [招募]       │ ┌─ 输入（支持 @） ─┐  │           │
│              │ └──────────────────┘  │           │
└──────────────┴──────────────────────┴───────────┘
```

### 5.2 招募成员（关键）

通讯录 sidebar 底部「招募」按钮打开选择器，**两种来源**：

| 来源 | 注入内容 | 适合场景 |
|---|---|---|
| **毛坯模板**（空壳） | 工作空间注入**全套**（prompt 前缀 / 模型默认 / 共享资源 / 上下文 / ……） | 想要简单，直接拿原型角色 |
| **用户的 Agent**（已装好） | 在 Agent 自带配置基础上**再注入空间级资源**（合并去重） | 想要专精，先调好再用 |

招进去后都成为**该空间的 Agent 实例**，跟源解耦。

### 5.3 通讯录 sidebar

- 列出该空间所有成员（管家固定第一位），每个显示头像 / 名字 / 状态
- 点击进实例详情：看配置、看注入内容、看在该空间的工作记忆（v2）

### 5.4 主对话区

- 每条 agent 回复气泡上**标注是哪个 agent 发的**（头像 + 名字）
- 用户输入框支持 **@mention** 唤出成员列表
- 长任务异步执行时显示进度气泡（"研究员正在分析 5 篇论文 3/5..."）

### 5.5 产出物面板

agent 工作过程产生的文档 / 数据 / 截图等沉淀在此，可单独管理、引用、下载。

### 5.6 沉淀（v2）

- 读：L1（用户画像）+ L2（空间世界观）+ L3（实例工作记忆）
- 写：用户对 agent 回复的修正 → 同步落 L3 patch；对空间整体的指示 → 落 L2

---

## 6. 路由规则（多 agent 调度）

### 6.1 三种路由分支

| 用户输入 | 路由 |
|---|---|
| **不 @ 任何人** | 走管家（管家决定派谁 / 自己回 / 接力多 agent） |
| **@ 某个成员** | **直接发给 TA**，管家不参与 |
| **@ 管家** | 跟管家直接对话 |

设计依据：@ 直连符合 Slack / 飞书 / Discord 的 @ 直觉。

### 6.2 管家（Supervisor）的能力

- 解析用户意图 → 派给合适的成员（LLM 调度，可加规则加权）
- 多 agent 接力（"研究员先调查 → 写手整理 → 校对最后过"）
- 临时 new subagent（用完即销毁）
- 整合多 agent 结果给最终回复

调度算法（纯 LLM / 规则 + LLM 混合）实施时定，预案：**规则优先 + LLM 兜底**。

### 6.3 Subagent 派生

管家判断"现有成员不够用"时，可基于某模板 + 父 agent 部分上下文 + 即时装备，临时 new 一个 subagent。

**生命周期**：用完即销毁，不进通讯录，对用户半透明（能在气泡上看到它在干活，但不能 @ 它、不能管理它）。复杂的留存生命周期 v1.5+ 再补。

---

## 7. 资源挂载（三层合并 + 注入引擎）

### 7.1 三层来源

| 层 | 来源 | 作用域 |
|---|---|---|
| **Agent 自带** | 用户在 `/agents` 给 Agent 挂的（如果招的是 Agent） | 该实例 |
| **空间共享** | 工作空间级别挂载 | 该空间所有成员 |
| **实例覆盖** | 实例在空间内额外挂载（实例的个性化） | 仅该实例 |

### 7.2 合并规则

agent 调用工具或查 RAG 时：**三层取并集去重**。

例：
- 用户的 Agent「代码研究员」自带 knowledge `{A, B, C, D}`
- 工作空间共享 knowledge `{A, B, C}`
- 实例在空间内额外挂 `{E}`
- → 该实例实际可见 `{A, B, C, D, E}`

不做"自动 push 到共享层"（避免自动迁移让用户搞不清来源）。实例 detail 里能看到来源分布。

### 7.3 注入引擎（v1 基础版，v2 上下文引擎）

工作空间不仅注入"资源"，还可以注入**任何配置**：

| 注入类型 | 例子 | v 几 |
|---|---|---|
| 资源 | knowledge / tool / MCP | v1 |
| Prompt 前缀 | "你在【博士项目】空间工作，目标是 X" | v1 |
| 默认模型 | 给毛坯模板招进来的成员指定默认 chat 模型 | v1 |
| 调用参数 | 给该空间所有成员注入 `temperature=0.3` | v1.5 |
| 上下文规则 | 该空间所有 agent 必须先查空间档案再回答 | v2 |
| 输出格式偏好 | 该空间偏好要点列举 | v2 |
| ……（开放扩展） | 新注入类型不需要改表结构 | 持续 |

实现机制：**JSON 字段保存所有注入内容**（详见 §10 数据结构设计原则）。

---

## 8. 长期记忆（沉淀 v2）

### 8.1 三层记忆

| 层 | 绑定 | 含义 | 谁能读 |
|---|---|---|---|
| **L1 用户画像** | `(user_id)` | 用户这个人的偏好 / 习惯 | Agent 模块 + 工作空间 都读 |
| **L2 空间世界观** | `(workspace_id)` | 空间整体氛围 / 目标 / 约束 | 仅该空间内读 |
| **L3 实例工作记忆** | `(workspace_id, agent_instance_id)` | 实例在该空间学到的偏好 | 仅该空间内读 |

### 8.2 跨场景规则

- **Agent 自身（模板/Agent/实例）无跨空间状态** —— 同一个模板在 A 空间和 B 空间是两个完全独立实例，互不相通
- 唯一跨场景的是 **L1 用户画像**
- L2 / L3 严格绑工作空间，空间删了 → 一起删

### 8.3 沉淀来源（v2）

- **显式信号**（同步落库，不要后台引擎）：
  - 用户改 agent 回答 → 抽 patch 落 L3
  - 用户说"以后这样" → AI 识别意图落规则
  - 用户对空间说"这里只做 X" → 落 L2
  - 用户上传素材 → 走 RAG 管线（复用知识库模块）
- **不做**：后台自动从对话历史总结提炼偏好（v2.5+ 再说）

### 8.4 v1 表结构预留

为避免 v2 加字段迁移，v1 建表时预留 JSON 占位：

```
workspaces.world_view         JSONField (null=True)   -- L2 占位
agent_instances.memory        JSONField (null=True)   -- L3 占位
users.profile_memory          JSONField (null=True)   -- L1 占位
```

v1 不读不写，仅占位。

---

## 9. 长任务异步 + 产出物

### 9.1 何时异步

- 用户布置的任务预计 > 30s（管家或 agent 自行判断）→ 自动转后台
- 用户也可显式标"后台跑"（输入框旁的"后台执行"开关）

### 9.2 进度可见

- 主对话区显示进度气泡（"研究员正在分析 5 篇论文 3/5..."）
- 用户可继续聊别的，进度气泡持续更新
- 完成后自动推送结果回复
- 后端用 ARQ + SSE 推进度，前端 streaming 更新气泡

### 9.3 产出物

- agent 任务产物（文档 / 数据 / 图表）= 时间线对象 + 沉淀到右侧产出物面板
- 可单独打开 / 下载 / 引用到下一次对话

---

## 10. 数据结构设计原则：Hybrid Schema + Context Injection ⭐

> 这是 agent 模块的**核心工程取舍**，决定了系统的扩展性边界。

### 10.1 业界叫法（产品 / 简历用）

- 产品 narrative：**Context Engineering** / **Context Injection**（2024-2025 AI 圈热词）
- 技术实现：**Configuration Composition with Hybrid Schema**（"配置组合 + 混合 schema"）

### 10.2 设计原则

**核心字段用普通列，扩展字段用 PostgreSQL jsonb**：

```
agents (用户的 Agent 资产):
  -- 核心字段（类型安全 + 索引友好）
  id, name, model_id, system_prompt, behavior_template, created_by, ...
  -- 扩展槽
  config: JSONField     -- 调用参数（temperature 等可扩展）
  metadata: JSONField   -- 元数据（icon, color, tags 等）

agent_instances (工作空间内成员):
  -- 核心字段
  id, workspace_id, source_template_id (nullable), source_agent_id (nullable), ...
  -- 扩展槽
  injections: JSONField  -- 工作空间注入的全部内容
  overrides: JSONField   -- 实例自己覆盖的个性化
  memory: JSONField      -- v2 长期记忆
```

### 10.3 为啥这么选（对照其他方案）

| 方案 | 灵活度 | 类型安全 | 查询性能 | 评价 |
|---|---|---|---|---|
| 大 JSON（schema-less） | 最高 | 无 | 差 | ❌ 类型乱，前端 TS 没法用 |
| EAV（Entity-Attribute-Value） | 高 | 弱 | 差 | ❌ join 噩梦 |
| **Hybrid（核心列 + JSON 扩展）** | 高 | 部分 | 好 | ✅ **采用** |
| Plugin / Hook 注册（运行时） | 高 | 强 | 好 | LangChain 那种，更重 |
| 全固定列 | 无 | 强 | 最好 | ❌ 每加能力一次迁移 |

### 10.4 为啥 Hybrid 最优

1. **类型安全够用**：核心字段（name / model_id / prompt）有列，前端 TS / 后端 Pydantic schema 明确
2. **扩展无迁移**：v2 加新注入类型（"工具调用风格"、"输出格式偏好"）只往 `injections` 加 key，不动表结构
3. **PostgreSQL jsonb 能查能索引**：`WHERE injections @> '{"style": "concise"}'` 走 GIN 索引，性能不差
4. **跟后端栈契合**：Tortoise ORM `JSONField` + PostgreSQL jsonb 是原生支持

### 10.5 反模式（避免）

- ❌ 啥都塞一个 `data: JSONField`（变 MongoDB，前端类型乱）
- ❌ EAV 全分散（每个属性一行，join 噩梦）
- ❌ 全固定字段（每加一个能力一次迁移）

### 10.6 跟业界产品对照

- **LangChain / LangGraph**：用 `Runnable` + `RunnableConfig`，Plugin 风格，不是 JSON
- **OpenAI Assistant API**：固定 schema（instructions / tools / model），扩展性差
- **CrewAI / AutoGen**：Pydantic dataclass，靠继承扩展
- **Dify**：工作流节点配置用大 JSON（schema-less），但应用层用固定 schema
- **MaxKB**：全固定字段，没扩展性
- **CoCoWork**：Hybrid Schema + Context Injection，**兼顾类型安全和扩展性**

---

## 11. Agent 调用流程：分层架构 + 设计模式 ⭐

> 这一节定义 agent 调用的运行时架构。**反对**把所有逻辑塞进 LangGraph 节点的糙做法，主张关注点分离 + 设计模式组合。

### 11.1 三层分离架构（Build-Execute-Postprocess）

agent 处理一条消息的完整流程拆成三层独立 service：

```
┌─────────────────────────────────────────────┐
│  Agent Runtime                              │
│                                             │
│  ① ContextBuilder（独立 Service）            │
│     - 合并三层资源（自带 / 共享 / 覆盖）       │
│     - 加载 L1/L2/L3 长期记忆                 │
│     - 拼装最终 prompt + context             │
│     → 输出准备好的 GraphInput               │
│                                             │
│  ② LangGraph Invocation（业务编排）          │
│     - 拿到准备好的 GraphInput               │
│     - 跑 graph（工具调用 / 多步推理 / etc） │
│     → 输出 GraphOutput                      │
│                                             │
│  ③ PostProcessor（独立 Service）             │
│     - 落库（消息历史 / Trace）               │
│     - 触发沉淀事件                            │
│                                             │
└─────────────────────────────────────────────┘
```

**核心立场**：LangGraph **只在中间层**用，专注业务编排；准备与后处理是独立 Service，可单独测试、跨 agent 模板复用。

### 11.2 七个核心设计模式

每个模式对应 CoCoWork 的一个真实问题，非堆砌。

#### 11.2.1 Layered Architecture（分层架构）

三层分离（§11.1）就是这个模式的落地。

#### 11.2.2 Builder Pattern（ContextBuilder Fluent API）

```python
context = (
    ContextBuilder()
    .for_agent(agent_instance)
    .in_workspace(workspace)
    .with_user_message(msg)
    .inject_resources()
    .inject_memories()
    .inject_workspace_rules()
    .apply_overrides()
    .build()
)
```

每步独立、链式调用、return self。可读性极佳，构造复杂对象的首选模式。

#### 11.2.3 Chain of Responsibility（注入责任链）

`ContextBuilder` 内部多种注入类型组织成责任链：

```
PromptInjector → ResourceInjector → MemoryInjector → WorkspaceRuleInjector → OverrideInjector
```

每个 Injector 实现统一接口：

```python
class Injector(Protocol):
    def inject(self, context: Context) -> Context: ...
```

**加新注入类型 = 加一个新 Injector 类，不动其他代码**（开闭原则）。v2 加上下文规则注入、v2.5 加输出格式注入，只是注入链多一节，零侵入式扩展。

#### 11.2.4 Strategy Pattern（行为模板 + 调度算法）

两处用：

**4a. 行为模板**：模板的 `behavior_type` 对应不同 Strategy
```python
class GraphStrategy(Protocol):
    def build_graph(self, agent: Agent) -> CompiledGraph: ...

class SingleAgentStrategy(GraphStrategy): ...
class SupervisorStrategy(GraphStrategy): ...
class PipelineStrategy(GraphStrategy): ...
```

**4b. 调度算法**：Supervisor 路由策略
```python
class RoutingStrategy(Protocol):
    def route(self, msg: Message, agents: list[Agent]) -> Agent: ...

class LLMRoutingStrategy(RoutingStrategy): ...
class RuleBasedRoutingStrategy(RoutingStrategy): ...
class HybridRoutingStrategy(RoutingStrategy): ...
```

跑起来后换算法不改业务代码。

#### 11.2.5 Mediator Pattern（Supervisor 的本质）

Supervisor 是 Mediator 的教科书例子：
- 多个 agent 之间不直接通信
- 都通过 Supervisor 中转
- 解耦 agent 间依赖
- 新增/移除 agent 不影响其他成员

#### 11.2.6 Repository Pattern（数据访问抽象）

Service 不直接碰 ORM，通过 Repository 拿数据：

```python
class AgentRepository:
    async def get_by_id(self, id: UUID) -> Agent | None: ...
    async def list_by_user(self, user_id: UUID) -> list[Agent]: ...

class MemoryRepository:
    async def load_l1(self, user_id: UUID) -> Memory: ...
    async def load_l2(self, workspace_id: UUID) -> Memory: ...
    async def load_l3(self, workspace_id: UUID, instance_id: UUID) -> Memory: ...
```

业务层只依赖接口，**单测 mock Repository 就行**，不启 DB。DDD 标配。

#### 11.2.7 Observer / Event-Driven（沉淀引擎解耦）

沉淀不硬塞主流程，做事件驱动：

```python
# Agent 业务层只发事件
await event_bus.publish(UserCorrectionEvent(
    user_id=...,
    instance_id=...,
    original_msg=...,
    corrected_msg=...,
))

# 沉淀引擎独立订阅
@event_bus.subscribe(UserCorrectionEvent)
async def extract_sediment(event: UserCorrectionEvent):
    patch = await llm.extract_pattern(event)
    await memory_repo.save_l3_patch(event.instance_id, patch)
```

**好处**：
- 沉淀引擎随时可关（不影响主流程）
- 一个事件多个订阅者（同时落 L3 + Trace + 通知）
- v2 加自动沉淀引擎 = 再加一个订阅者

### 11.3 三个高阶架构概念

#### 11.3.1 Hexagonal Architecture / Ports & Adapters

业务核心通过 Ports（接口）跟外部解耦：

```
[LLM Port]     ← OpenAIAdapter / DashScopeAdapter / AnthropicAdapter
[Storage Port] ← LocalStorageAdapter / R2Adapter
[Vector Port]  ← PgvectorAdapter
[Memory Port]  ← PostgresMemoryAdapter (v2 可换 Redis / 专用 memory store)
```

换 LLM provider 只换 Adapter，业务核心零改动。Clean Architecture 的核心。

#### 11.3.2 Event-Driven Architecture (EDA)

沉淀提取、长任务进度、通知 push、可观测 trace 全部走事件总线：
- 内部：`asyncio.Queue` 或 in-process pub/sub
- 跨进程：Redis Streams 或 ARQ task queue（已规划）

#### 11.3.3 CQRS（可选，v2+）

- Command 侧（写）：agent 调用、沉淀写入、消息持久化 —— 关键路径，强一致
- Query 侧（读）：agent 列表、记忆查询、工作空间档案 —— 可缓存，可异步

v1 不上完整 CQRS（过度设计），但**保留分离的可能**。

### 11.4 简历叙述版（一段话讲完整套架构）

> CoCoWork agent 模块采用 **Hexagonal Architecture**，业务核心通过 Ports 与 LLM / Storage / Vector DB 解耦。Agent 调用流程采用 **三层分离架构**（Build-Execute-Postprocess），ContextBuilder 用 Builder + Chain of Responsibility 组织多种注入类型，行为骨架与调度算法用 Strategy 模式抽象。Supervisor 作为 Mediator 协调多 agent，沉淀引擎通过 Event-Driven Architecture 解耦主流程。数据访问走 Repository Pattern，便于单测与 DB 切换。

### 11.5 反模式（明确避免）

| 反模式 | 为啥不做 |
|---|---|
| ❌ 把上下文注入塞进 LangGraph 节点 | 准备与执行混淆，违反单一职责；跨模板难复用；测试痛苦 |
| ❌ Service 直接调 ORM | 难单测，DB 替换困难，违反依赖倒置 |
| ❌ 沉淀逻辑硬塞主调用流 | 强耦合，沉淀不能关；新增订阅者要改主流程 |
| ❌ LLM provider 紧耦合（直接 import openai） | 换 provider 大改业务；测试要真打 LLM |
| ❌ 大 JSON 啥都塞 | 类型丢失、前端 TS 用不了、查询性能差 |
| ❌ 全固定字段 | 每加新能力一次迁移 |

---

## 12. v1 切片大纲

按"骨架先立、能力后加"原则，10 片小步推进；每片做完都跑通一段端到端：

| 片 | 内容 | 前/后 |
|---|---|---|
| **0**（前置） | 前端基建：nav 加 Workspace / Workspace 占位 / Agent 模块三带式骨架 / 详情页左配右聊骨架 | 前端 |
| **1** | Agent 模板系统：seed 5-8 个内置模板（纯行为骨架）+ 模板池只读 API + 列表展示 | 全栈 |
| **2** | Agent 数据模型 + CRUD（基于模板创建用户 Agent，含 prompt / 模型 / 资源挂载） | 全栈 |
| **3** | Agent 模块详情页（左配 + 右聊，单 agent 跑通对话，正常 + 调试两种模式） | 全栈 |
| **4** | Workspace 数据模型 + CRUD | 后端 |
| **5** | 工作空间招募：选模板（注入）或选 Agent（注入合并），生成实例 | 全栈 |
| **6** | 工作空间详情页（通讯录 + 主对话基础链路 + 气泡 agent 标注） | 全栈 |
| **7** | Supervisor 多 agent 调度（LangGraph） + @mention 路由 | 全栈 |
| **8** | 长任务异步执行 + 进度气泡（ARQ + SSE） | 全栈 |
| **9** | Subagent 运行时 new | 全栈 |
| **10** | 产出物面板 + 时间线对象 | 全栈 |

**v2（沉淀）单独规划**：三层记忆表激活 + 显式信号落库 + 读取合并逻辑。

---

## 13. 决策回顾（why-not 备忘）

| 决策 | 理由 |
|---|---|
| 不做发布 / 快照 | CoCoWork 是个人/团队工具，不是给陌生人用的 SaaS；调试和真使用合二为一，消解二元状态 |
| 单 agent 也做独立入口 | 不强迫用户上工作空间；轻量场景直接走 Agent 模块 |
| 模板/Agent/实例 三层分离 | 模板是空壳骨架（平台维护）；Agent 是用户资产（可独立用）；实例是空间成员（带空间注入） |
| 模板不可编辑 | 模板是质量保证 baseline（平台运营），用户能装备但改不了行为骨架 |
| @ 直连而非管家路由 | 符合 Slack / 飞书 @ 直觉，多一层 supervisor 中转反直觉 |
| 不让用户改 graph | 行为复杂度高、用户写不好；prompt 已经足够暴露调节面 |
| Subagent 用完即销毁 | v1 简单；少数"留下"场景 v1.5+ 再加 lifecycle 字段 |
| 沉淀 v2 才做 | 先让骨架跑起来再加增强；沉淀引擎落地的产品形态还需观察 |
| 长期记忆只绑 (user) / (workspace) / (workspace+instance) | agent 自身无跨空间状态；唯一跨场景的是用户画像 |
| 资源三层合并取并集去重，不自动 push | 避免自动迁移让用户搞不清来源；保留显式覆盖 |
| Hybrid Schema 而非纯 JSON / 纯固定字段 | 兼顾类型安全和扩展性（详 §10） |

---

## 14. 高阶补强清单（v1.5+ / 简历加分项）⭐

> 当前 spec 跑通后，按这清单逐项补强，把项目从"个人作品"推到"架构师视角"。

### 14.1 可观测性（Observability）

- 每次调度决策落 trace（管家选了谁 / 为啥选 / 耗时）
- agent 调用链可视化（用户消息 → supervisor 决策 → agent 1 → tool call → agent 2 → 最终回复）
- 注入链可审计（这次调用注入了哪些资源、哪些 prompt 前缀、来自哪一层）
- 工具：先用结构化日志（`structlog` / `logging`），后期接 OpenTelemetry / Langfuse

### 14.2 演进路径（Evolution）

为简历讲故事，在 README 写「v1 → v2 → v3 演进路径」：

- **v1**：骨架（当前 spec 内容）
- **v1.5**：可观测性 + 调度规则可配 + subagent 留存
- **v2**：沉淀引擎（L1/L2/L3 三层记忆 + 显式信号落库）
- **v2.5**：后台沉淀引擎（异步抽取 + 偏好衰减）
- **v3**：多模态 / 跨工作空间共享 Agent / 公开链接（如有需求）

**数据结构平滑迁移**：v1 已预留 JSON 占位字段，v2 不破坏表结构。

### 14.3 量化指标（Metrics）

跑起来后填，简历有数字加分：

- 单次调度成本（LLM token / 美元）
- 端到端响应时延（P50 / P95 / P99）
- 多 agent 接力 vs 单 agent 直答的质量对比（人工评测样本）
- 注入合并耗时（资源去重算法性能）
- 工作空间单次会话平均成员数 / 平均 turn 数

### 14.4 真实场景案例（User Story）

README 里放一两个最长 user story，让架构落地具体场景：

> **Alice 是博士生**，建了"博士论文项目"工作空间。招了"研究员"（毛坯模板，空间注入了 RAG 索引的 200 篇论文）+ "写手"（她在 Agent 模块调好的 Agent，自带学术写作偏好）。她说"分析最近 5 篇 transformer 综述"，管家派给研究员；研究员遇到一段数学公式，临时 new 一个"数学家" subagent 算出来；分析完研究员把要点交给写手，写手按 Alice 之前的学术风格组织成段落。Alice 中间修正了写手的一句话措辞 → 落入 L3，下次该写手在该空间自动用新措辞。

### 14.5 容错与降级

- LLM 调用失败 → 降级到规则路由 / 静态回复
- 工具调用超时 → 提示用户 + 不阻塞其他 agent
- 沉淀写入失败 → 不影响主对话流（fire-and-forget）

### 14.6 安全与隔离

- 跨工作空间的资源/记忆隔离（即使同用户也严格隔离）
- 工具调用沙盒（外置 skill / MCP 不污染主进程）
- 用户上传素材的内容审查（v2）

---

## 附录 A：术语表

| 术语 | 解释 |
|---|---|
| **模板 (Template)** | 平台内置的"职业类型"，纯 LangGraph 行为骨架，空壳，不可编辑 |
| **Agent** | 用户在 /agents 基于模板创建的资产，含 prompt / 模型 / 资源 |
| **Agent 实例** | 工作空间内的成员，由模板或 Agent 复制 + 空间注入而来 |
| **管家 / Supervisor** | 每个工作空间的默认 agent，负责调度 |
| **Subagent** | 管家临时派生的子 agent，用完即销毁 |
| **L1 / L2 / L3** | 三层长期记忆：用户画像 / 空间世界观 / 实例工作记忆 |
| **资源三层** | Agent 自带 / 空间共享 / 实例覆盖 |
| **行为模板** | LangGraph 内置的几种 graph 拓扑（single / supervisor / pipeline 等） |
| **注入引擎** | 工作空间给招进来的 agent 实例注入资源 / prompt / 上下文 / 规则的机制 |
| **Hybrid Schema** | 核心字段用 SQL 列 + 扩展字段用 PostgreSQL jsonb 的混合方案 |
| **Context Engineering** | 业界对"给 LLM 喂上下文"工程实践的统称，CoCoWork 的注入引擎是其落地 |

---

## 附录 B：跟同类产品技术对照（详版）

| 产品 | 多 agent 实现 | 配置存储 | 扩展点 |
|---|---|---|---|
| MaxKB | 单 agent | 固定字段 | 工具配置可扩 |
| Dify | 工作流画布（节点编排） | 节点配置 JSON | 节点类型可扩 |
| FastGPT | 工作流 + 单 agent | 配置 JSON | 弱 |
| LangChain / LangGraph | Runnable / Graph | Python 代码 | Runnable 可组合 |
| AutoGen / CrewAI | 多 agent 框架（SDK） | Python dataclass | 继承扩展 |
| OpenAI Assistant API | 单 assistant | 固定 schema | tools 注册 |
| Claude Code | 后台 Task tool | 内部 | 工具/MCP |
| **CoCoWork** | **同会话多 agent 接力 + @ 直选** | **Hybrid Schema** | **注入引擎（可加任意注入类型）** |
