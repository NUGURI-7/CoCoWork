# 内置模板（Built-in Template）设计 v1

> 范围：**内置模板这一层**到底装什么、按什么区分、要几个。只管「出厂自带的图配方」，**不含**用户创建 Agent（实例 / NPC）时挂的知识库 / 用户工具 / skill / 能力开关 —— 那些是实例层，模板碰不到。
> 地基约束见 `../architecture.md`（尤其 §7 Agent 模型、§7.1「图壳默认有、节点按需填」、§8 功能落点）。
>
> 编写时间：2026-06-03
> **v1.1 修正（同日）**：loop 侧由「k 条预设模板」收敛为「**1 个可配置引擎**」；能力（middleware / 工具束）从模板区分轴**下放到实例层、做成可组合开关**。结论：结构 = **1 + N**。

---

## 1. 一条主线：内置模板 ≠ 成品

- **内置模板** = 进程启动时编好、全平台共享的**图配方**，workspace 无关。它能携带的只有「出厂代码 / 数据」。
- **成品（实例 / NPC）** = 用户基于内置模板，挂知识库 + 用户工具 + skill + **勾能力** + 填 prompt 后的产物，存在 `agents` 表。
- **铁律**：知识库 / 用户工具 / skill / **能力开关** 都是**实例层**字段，内置模板**碰不到**，因此**不能**靠它们区分模板。

> 推论：医生 / 老师 / 律师**不是内置模板**。在模板层它们都是同一个 loop 引擎，只有用户挂了医学 / 教材知识库 + 设了 prompt（+ 勾了能力）之后才变成「医生」「老师」。它们不占模板名额。

---

## 2. 模板级能区分的，其实只有 graph 拓扑

> **v1.1 核心修正**：能力 / 工具 / prompt 都**不是**模板级区分轴——它们可组合 / 可填，归实例层。模板层真正不可组合、必须用代码固化的结构，**只有 graph 拓扑**。

| 维度 | 归属 | 是模板级区分吗 |
|---|---|---|
| **graph 拓扑**（节点 / 边 / 固定流程） | 出厂代码 | ✅ 唯一的模板级结构区分（仅 graph 侧） |
| **能力 middleware**（强制搜索 / reflection…） | 可组合 | ❌ 实例层开关，见 §4 |
| **内置工具束**（sandbox / 文件系统…） | 可组合 | ❌ 实例层开关 |
| **base_prompt** | 可填 | ❌ 实例层覆盖 / 追加 |
| 知识库 / 用户工具 / skill | 实例层资源 | ❌ 模板层不存在 |

> **为什么能力不是模板轴**：强制搜索、反思、沙箱……这些是**可叠加的积木**——一个 agent 完全可能同时要检索 + 沙箱 + 反思。把它们做成互斥模板（选一个排斥另俩），正是「把可组合能力当分类格子」的反模式（§8）。

---

## 3. 结构 = 1 + N

| | 1（loop 侧） | N（graph 侧） |
|---|---|---|
| **是什么** | **一个**可配置 loop 引擎（一份 `create_agent` 工厂） | N 份手写 `StateGraph` |
| **变量从哪来** | prompt / tools / model / 能力 middleware **全由 config 装配**，引擎代码不变 | 每份是固定流程的节点 / 边代码 |
| **性质** | 引擎一份；「花样」靠装配，**廉价**（加能力 = 注册表加一条；加预设 = 加一条 config） | **代码，贵**，每加一个是真活 |
| **数量** | **1** | 越少越好，只给**真需要固定流程**的；首批可 0 |

**原则：能用「loop 引擎 + 能力装配」解决的，就别写 graph。** graph 只留给真正不可组合的固定拓扑。

---

## 4. 能力可组合：注册表 + config + 装配器

loop 引擎跑前，它的 middleware 列表是**现拼**的，分两层：

```
最终 middleware 列表 =
    [ 统一层：WorkspaceContext / 记忆作用域 / 模型分级 / 记账 ]   ← 每个 agent 都有，装配器写死
  + [ 能力层：按 config.capabilities 勾的，按固定顺序 ]           ← 可叠加 / 可拆卸
```

三件套（plugin 模式，无魔法）：

1. **能力注册表**：`能力 key → 产出该 middleware 的工厂`（如 `"forced_search" → ForcedSearchMiddleware`）。新增一种能力 = 注册表加一条，别处不动。
2. **config 声明**：实例 `config.capabilities = ["forced_search", "reflection", ...]`。勾哪些 = 改这个列表（去掉一项 = 拆掉一个能力）。
3. **装配器**：跑前读 config → 按 `capabilities` 查注册表 → 按固定顺序拼成列表 → 喂 `create_agent(middleware=[...])`。顺序由装配器维护（middleware 是 onion，序不能乱）。

> **工业对照**：Dify / Coze 的「联网搜索 / 代码解释器 / 知识检索」就是 bot config 的 toggle，运行时装配——一个引擎 + 一组可勾能力 + 一个装配器，不为每种组合写类。CoCoWork 一模一样。

---

## 5. 模板字段结构（按名字 + 类型，非代码）

> 每个内置模板 = 一条注册项，注册进 `app/agents/templates/`。`Agent.template` 存这里的 `key`。**能力不在模板字段里**（见 §4，归实例 config）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `key` | str | 稳定标识，存 `agents.template`，创建后锁死 |
| `name` / `description` | str | 展示用 |
| `form` | `"loop" \| "graph"` | loop = 那个可配置引擎；graph = 手写图 |
| `base_prompt` | str | 出厂提示词脚手架；实例 prompt 覆盖 / 追加 |
| `builtin_tools` | list[str] | 引擎自带的**基础**内置工具 key（差异化工具束归实例可组合，不在此） |
| `recommended_slots` | list[...] *(可选)* | 仅元数据 / 提示，建议实例挂什么类型知识库；**不挂实物** |

- **loop**：就一条（`form="loop"`），即那个引擎；**不带 capability**，能力靠 §4 装配。
- **graph**：每条额外提供一份手写 `StateGraph`（`form="graph"` + `build()`）。

> 代码落点：`base.py` 的 `LoopTemplate` / `GraphTemplate` 两支基类已就位；v1.1 把 `LoopTemplate.capability_middleware` 字段**移除**（挪进实例 config）。

---

## 6. 内置模板清单（首批，1 + N）

### 1（loop 侧）

就**一个**：**通用 loop 引擎**（key 暂定 `general`），即 Augmented LLM 基线。所有 loop 型 agent 都用它，差异全靠实例 config（prompt / 挂载 / 勾能力）。

> 旧版的「检索增强型 / 构建型 / 反思型」**不再是模板**，而是实例勾的能力（§4）。将来若要方便，可做成**「预设」= 一组默认勾选的能力**（纯 config 数据，非模板，可勾完再改）。

### N（graph 侧，极少，按需才加）

只给**真需要确定性固定流程**的角色（如合规审查、结构化报告）。命名对齐 Anthropic 5 个 workflow 模式（prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer）。**首批为 0**，功能到了再加。

---

## 7. 与现有 Agent 模型的衔接（不返工）

- `agents.template`（CharField）= 本设计的 `key`（loop 恒为那个引擎 key；graph 为对应 graph key）。✅ 已就位。
- `agents.config`（JSONField）= **实例层填料**，与模板字段互补、不重叠：
  - 行为：loop → `{prompt, model}`；graph → `{nodes: {<节点名>: {prompt, model}}}`
  - 资源：`knowledge / tools / skills` 的 id 列表（实例层独有）
  - **能力（v1.1 新增）**：`capabilities: [...]` —— 实例勾的能力 key 列表，装配器据此拼 middleware
- **跑前装配**：拿 `key` → loop 取那个引擎 / graph 取那份图 → 叠加统一横切 middleware → **按 `config.capabilities` 装配能力层** → 注入 config（prompt / model / 资源）→ 产出 `CompiledStateGraph`。

---

## 8. 权威依据（一句话）

Anthropic《Building Effective Agents》：一级只分 **Workflow（图）vs Agent（loop）**；基线是 **Augmented LLM = LLM + 工具 + 检索 + 记忆**，「大多数应用一个就够，别过度设计」；能力是**可组合的积木，不是互斥分类格子**。→ 直接对上本设计：**1 个可配置 loop 引擎（能力靠装配叠加）+ 少数 graph 例外（N）**，**不按职业、也不按能力组合建分类法**。

---

## 9. 留的口子 / 本期不做

- graph 模板首批为 0，不硬凑。
- **能力注册表 + 装配器的具体实现**随各能力 middleware 落地时回填；现在 `config.capabilities` 先存 key 占位、不解析。
- **差异化内置工具束**（sandbox / 文件系统）的实例装配机制（走 `capabilities` 统一通道，还是独立 tool-toggle）待实现时定。
- **「预设」**（默认能力组合）是否做、前端怎么呈现，待 agent 模块前端联动时定。
- `recommended_slots` 的展示形态（前端怎么提示）属前端范畴，本文不定。
