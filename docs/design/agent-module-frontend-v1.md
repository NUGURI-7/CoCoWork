# CoCoWork Agent 模块 — 前端画法指南 v1

> 本文档是 agent 模块前端实施的"作业本"，纯前端骨架画法，**不接 API、全 mock + local state**。后端齐了再把 mock 换成真实接口，组件结构不重画。
> 主 spec 见 `agent-module-v1.md`，本文档只关心"前端画什么、怎么画、怎么交互"，**不涉及具体代码**。
>
> 编写时间：2026-05-26

---

## 0. 范围声明

### 0.1 这份文档干啥的

- 给前端开发者（或 AI 协作者）一份**自包含**的画法指南：照着这份 + 主 spec，能完整画出 agent 模块前端骨架
- 不涉及后端、API、数据库
- 不涉及具体代码，只描述布局、组件、交互、视觉

### 0.2 范围

✅ 包含：
- nav / 路由结构
- 列表页 + 详情页 + 弹窗 的布局描述
- 类型层字段清单（按名字 + 类型描述，非代码）
- Mock 数据**内容**清单（5-8 个模板等具体应该有啥）
- 交互细节（hover / click / disabled / 切换）
- 实施分批建议

❌ 不包含：
- 代码片段
- API 接口设计
- 后端表结构

### 0.3 实施前置阅读

1. `docs/design/agent-module-v1.md` —— 主 spec，了解整体设计 + 心智
2. `docs/context.md` —— 项目当前状态
3. `CODING-STYLE.md` —— 项目编码规范
4. `CLAUDE.md`（根目录）—— 项目说明 + 图标 / Tailwind / 品牌色等约定

---

## 1. 文件清单

### 1.1 路由层（新增 + 改造）

| 路径 | 状态 | 说明 |
|---|---|---|
| `routes/_authenticated/workspaces.tsx` | 新建 | Outlet 布局壳 |
| `routes/_authenticated/workspaces/index.tsx` | 新建 | PagePlaceholder 占位（无功能） |
| `routes/_authenticated/agents.tsx` | 保留 | Outlet 布局壳，不动 |
| `routes/_authenticated/agents/index.tsx` | 不动 | 继续 import `AgentsPage` |
| `routes/_authenticated/agents/$agentId.tsx` | 改造 | 从 PagePlaceholder 换成 `AgentDetailPage` |

### 1.2 导航配置（改造）

| 文件 | 改动 |
|---|---|
| `components/layout/nav.config.ts` | 在 `Agents` 之上新增 `Workspace` 项 |

### 1.3 类型层（重写）

| 文件 | 改动 |
|---|---|
| `types/agent.ts` | 整个重写（删旧 status/agent_type，加 Template / 新 Agent 字段） |
| `types/index.ts` | 同步 export |

### 1.4 Agent 模块组件（新建 + 改造）

| 文件 | 状态 | 说明 |
|---|---|---|
| `pages/agents/AgentsPage.tsx` | 重写 | 三带式：Header + 模板池横向带 + 我的 Agent 网格 |
| `pages/agents/AgentCard.tsx` | 改造 | 移除 status/对话按钮，改字段 |
| `pages/agents/TemplateCard.tsx` | 新建 | 模板池横向带里的小卡片 |
| `pages/agents/CreateAgentDialog.tsx` | 新建 | 创建弹窗（选模板 + 起名） |
| `pages/agents/AgentDetailPage.tsx` | 新建 | 左配 + 右聊详情页 |
| `pages/agents/ConfigPanel.tsx` | 新建 | 详情页左栏（可拆可不拆，组件大才拆） |
| `pages/agents/Playground.tsx` | 新建 | 详情页右栏（同上） |
| `pages/agents/mock.ts` | 重写 | 模板 / Agent / 模型 / 知识库 / 工具 全套 mock |

### 1.5 收尾（可选放后批）

| 文件 | 改动 |
|---|---|
| `pages/Home.tsx` | 把 dashboard 卡片 "Agents" 改成 "工作空间 + Agent 模板" 两组数字 |

---

## 2. 前端类型层（字段清单）

> 以下按名字 + 类型 + 必填描述，**不写代码**。实施时按项目 TS 风格组织。

### 2.1 Template（平台预置模板，前端只读）

- `id`: string
- `name`: string —— 显示名（"研究员"、"写手"）
- `behavior_type`: enum —— `single` / `supervisor` / `pipeline` / `react` 等
- `description`: string —— 一句话
- `icon`: string —— Lucide icon 名（"Search" / "PenTool" / "ClipboardCheck"）
- `default_avatar_color`: string —— 给基于此模板创建的 Agent 一个默认头像底色

### 2.2 Agent（用户资产）

- `id`: string
- `name`: string —— 用户起的名
- `template_id`: string —— 引用的模板
- `template_name`: string —— 冗余，省得每次 join（前端只用）
- `behavior_type`: enum —— 从模板带过来，只读展示
- `avatar_color`: string —— 头像底色（创建时从模板默认色继承，可改）
- `description`: string —— 用户自填
- `model_id`: string | null —— 必填业务上，但 mock 允许 null
- `model_display_name`: string | null —— 同上
- `system_prompt`: string | null —— 非必填
- `config`: object —— 调用参数（temperature / top_p / max_tokens 等）
- `knowledge_ids`: string[]
- `tool_ids`: string[]
- `mcp_ids`: string[]
- `created_at`: string (ISO)
- `updated_at`: string (ISO)

### 2.3 ChatModel（mock 引用，对齐已有 Model 模块）

沿用 `types/model.ts` 中的 `AIModel`，前端 mock 几条就行。

### 2.4 KnowledgeBase / Tool（mock 引用）

沿用 `types/knowledge.ts`、暂无 tool 类型则补一个 mock 形态：`{ id, name, type, icon }`。

### 2.5 Message（详情页右栏对话）

前端单 agent 沙盒试运行的消息类型（mock，本地 state）：
- `id`: string
- `role`: `'user' | 'assistant'`
- `content`: string
- `created_at`: string

详情页右栏只做**沙盒试运行**，消息不持久化（卸载 / 刷新即清）。正式对话归 workspace 模块，不在 agent 详情页做。

---

## 3. Mock 数据内容清单

### 3.1 模板池（5-8 个）

| name | behavior_type | icon (Lucide) | description |
|---|---|---|---|
| 研究员 | single | Search | 信息检索、文献查阅、要点归纳 |
| 写手 | single | PenTool | 文字创作、文案润色、风格调整 |
| 校对 | single | ClipboardCheck | 语法校对、事实核查、逻辑审视 |
| 调查员 | react | Telescope | 主动多轮查找、对比、追问 |
| 翻译 | single | Languages | 多语种翻译，保持术语一致 |
| 数据分析师 | pipeline | BarChart3 | 数据清洗、统计、可视化建议 |
| 编程助手 | react | Code2 | 代码理解、调试、解释 |
| 产品经理 | supervisor | LayoutDashboard | 需求拆解、用户故事编写 |

5 个起步够用，可全列。模板不可编辑（在 UI 上不显示编辑入口）。

### 3.2 我的 Agent（3-5 个）

示例：
- `代码研究员` —— template_id 指向 `编程助手`，挂了 1 个 knowledge（"内部 API 文档"）+ 2 个 tool
- `营销文案手` —— template_id 指向 `写手`，挂了 1 个 knowledge（"品牌词库"）
- `论文翻译` —— template_id 指向 `翻译`，模型 = GPT-4 / Qwen Plus
- `周报生成` —— template_id 指向 `产品经理`，挂了 knowledge
- 一个无 prompt 无资源的"裸 Agent"（验证空态显示）

### 3.3 ChatModel（mock 3-5 个）

GPT-4 / Qwen Plus / DeepSeek Chat / Claude Sonnet / 本地 Llama —— 跟项目已有 Model 模块的真数据风格一致即可。

### 3.4 Knowledge / Tool（各 2-3 个 mock）

引用项目 `pages/knowledge/mock.ts`、`pages/tools/mock.ts` 已有数据，或新建几条专用 mock。

---

## 4. Agent 列表页（三带式）

路径：`/agents` → `AgentsPage`

### 4.1 整体布局

```
┌────────────────────────────────────────────────────────┐
│  ① Header                                              │
│  Agents                          [+ 创建 Agent]        │
├────────────────────────────────────────────────────────┤
│  ② 模板池横向卡片条（只读）                              │
│  从模板开始：                                            │
│  [研究员] [写手] [校对] [调查员] [翻译] [数据] →→→      │
├────────────────────────────────────────────────────────┤
│  ③ 我的 Agent 卡片网格                                   │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐               │
│  │ A    │  │ B    │  │ C    │  │ D    │               │
│  └──────┘  └──────┘  └──────┘  └──────┘               │
└────────────────────────────────────────────────────────┘
```

### 4.2 第一带 Header

- 左：标题 "Agents"（同 Knowledge / Models 风格，字号、字重对齐）
- 右：`+ 创建 Agent` 按钮（shadcn `Button`，size sm）
- 点击「创建 Agent」→ 打开 `CreateAgentDialog`

### 4.3 第二带 模板池横向卡片条

- 标题文案："从模板开始" 或 "平台模板"（小一号字体，灰色，类似分组标题）
- 横向滚动容器（overflow-x-auto，scroll-snap 可选）
- 每张模板卡片宽约 200-240px，紧凑
- 单卡内容：
  - 顶部 icon（Lucide，颜色用品牌色 `text-brand`）
  - 模板名（粗体）
  - 一句话描述（line-clamp-2，灰色）
  - 底部小 badge：`behavior_type`（用 secondary variant 的 Badge）
- 卡片样式：`card-interactive` 包一层（hover 上浮 + 边框转墨绿）
- 点击模板卡 → 直接打开 `CreateAgentDialog` 且预选该模板

### 4.4 第三带 我的 Agent 卡片网格

- grid 布局，`grid-cols-[repeat(auto-fill,minmax(320px,1fr))]`
- 每张 Agent 卡片（`AgentCard`）见 §4.6
- 空态：当 mockAgents 为空 → 显示引导
  ```
  ┌────────────────────────────────┐
  │  [icon: Bot]                   │
  │                                │
  │  你还没创建 Agent                │
  │  从上方模板开始装备一个          │
  │                                │
  │  [创建 Agent]（按钮）            │
  └────────────────────────────────┘
  ```
  - 居中、虚线边框、灰色，类似 Knowledge / Tools 空态

### 4.5 头部说明文案（可选）

第一带和第二带之间，可加一行说明：
> "Agent 是你基于模板装备的资产 —— 选模型、写 prompt、挂知识库和工具。创建好的 Agent 可在工作空间里招募协作。"

字号小、灰色、不抢戏。给新用户做心智引导。

### 4.6 AgentCard（我的 Agent 单卡）

布局（参考项目已有 `KnowledgeCard` / `ProviderCard` 风格）：

```
┌─────────────────────────────────────────┐
│ [头像/icon]    Agent 名                 │
│                template_name · 一句描述  │
├─────────────────────────────────────────┤
│  🤖 模型名 · 📚 N 知识库 · 🔧 M 工具    │
├─────────────────────────────────────────┤
│  更新于 X 天前                           │
└─────────────────────────────────────────┘
```

- 头像：圆形，使用 `avatar_color` 作底色 + 首字母 / 模板 icon
- Agent 名加粗
- 第二行小字灰色：`template_name + " · " + description (line-clamp-1)`
- 中间一行 meta：模型 / 知识库数 / 工具数，用小 icon + 数字
- 底部：相对时间
- 整卡 `card-interactive`，点击 → 进 `/agents/$id`
- **不再有"对话"按钮**（点卡片就进详情页，详情页就是配置 + 对话）
- **不再有 published/draft badge**

右上角放三点 dropdown（仿 ProviderCard / KnowledgeCard）：
- "编辑"（跳详情）
- "复制为新 Agent"（占位，v1 可禁用）
- "删除"（AlertDialog 二次确认，仅本地 state 移除）

---

## 5. 创建 Agent 弹窗（CreateAgentDialog）

打开时机：
- 点 Header「创建 Agent」按钮
- 点模板池里某张模板卡（预选该模板）
- 点空态的「创建 Agent」按钮

### 5.1 布局

shadcn `Dialog`，宽度约 600px：

```
┌─────────────────────────────────────────┐
│  创建 Agent                              │
│  选一个模板，起个名字                      │
├─────────────────────────────────────────┤
│  ① 选择模板                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │ 研究员│ │ 写手 │ │ 校对 │ │ 调查员│   │
│  └──────┘ └──────┘ └──────┘ └──────┘    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │ 翻译 │ │ 数据 │ │ 编程 │ │ PM   │    │
│  └──────┘ └──────┘ └──────┘ └──────┘    │
│                                         │
│  ② 起个名字                              │
│  [输入框：我的研究员]                     │
│                                         │
│  [取消]              [创建]              │
└─────────────────────────────────────────┘
```

### 5.2 行为

- 模板选择：grid，每个小卡（icon + 名字），点击选中，选中态加品牌色边框 + `bg-brand-subtle`
- 名字输入：默认值 = "我的" + 模板名（如选了"研究员" → 默认 "我的研究员"），用户可改
- 创建按钮：选模板 + 名字非空才启用
- 点击创建：v0 阶段 toast 提示 + close，**不真创建**（等切片 2 接 API）
  - v0 实施时也可以让它真的 push 到 local state 的 mockAgents 里，方便看效果

---

## 6. Agent 详情页（左配 + 右试运行）

路径：`/agents/$agentId` → `AgentDetailPage`

> **定位（重要）**：详情页是**创作者视角**——装备配置 + 沙盒试运行。**不做正式对话**：单 agent 的正式对话归 workspace 模块（终端用户在工作空间里招募 agent 后对话），避免「同一对话能力两个入口」的心智冲突。右栏 Playground 因此只有一种模式 = 沙盒，消息不持久化。

### 6.1 整体布局

固定左 40% / 右 60%，无模式切换、无收起动画。

```
┌──────────────────────────────────────────────────────────┐
│ 顶部 Breadcrumb:  ← Agents / 代码研究员                     │
├──────────────────────┬───────────────────────────────────┤
│ 左栏 配置（40%）      │ 右栏 沙盒试运行（60%）             │
│ 可滚动                │                                   │
│                      │  ┌─ 消息区 ──────────────────┐    │
│  头像 + 名字 + badge  │  │ 你: ...                  │    │
│  描述                 │  │ Agent: ...               │    │
│  ─────────────        │  │ ...                       │    │
│  模型 ⓘ              │  └──────────────────────────┘    │
│  ─────────────        │                                   │
│  调用参数（折叠）       │  ┌─ 输入区 ───────────────┐      │
│  ─────────────        │  │ [输入框]    [发送]      │     │
│  System Prompt        │  └────────────────────────┘      │
│  ─────────────        │                                   │
│  知识库                │                                   │
│  ─────────────        │                                   │
│  工具 / MCP           │                                   │
└──────────────────────┴───────────────────────────────────┘
```

### 6.2 左栏（ConfigPanel）

#### 6.2.1 顶部

- 顶部 breadcrumb：`Agents / [Agent 名]`，点 Agents 跳回列表
- 头像（圆形，`avatar_color` 底色 + 首字母）
- 名字（Input，可改，失焦保存 to local state）
- 描述（Textarea，2 行，可改）

#### 6.2.2 字段顺序（spec §4.2 对齐）

1. **基础**：名字 / 头像 / 描述
2. **行为模板**：badge 形式只读展示（"single" / "react" / "supervisor" 等），鼠标 hover 提示"行为模板创建时选定，不可改"
3. **模型**：shadcn `Select`，选项来自 mockChatModels；右侧有个小 `ⓘ` tooltip "必填——不配模型没法调 LLM"
4. **调用参数**（折叠，shadcn `Accordion`，默认收起）：
   - temperature：Slider 0-2，步长 0.1，默认 1
   - top_p：Slider 0-1，步长 0.05，默认 1
   - max_tokens：Input number 类型，默认 1024
5. **System Prompt**：大 Textarea，min-h-32，可拉伸；占位文案"留空 = 使用模板默认行为"
6. **知识库**：多选关联组件（v0 可用 shadcn `Command` + `Popover`，或简单 Checkbox 列表）
7. **工具 / MCP**：同 6，可用同组件复用

#### 6.2.3 保存即生效（关键交互）

- **无"保存"按钮**
- 各字段失焦 / change 触发本地 state 更新
- 右栏对话用最新 state（下一条消息生效）
- 顶部小灰字提示"配置变更即时生效"（淡淡显示，可选）

### 6.3 右栏（Playground · 沙盒试运行）

**只有一种模式 = 沙盒**，无 tab、无 banner。消息纯内存，刷新 / 离开页面即清。

#### 6.3.1 消息区

- 滚动容器，flex-1
- 用户气泡：右对齐，普通边框 + 浅背景
- Agent 气泡：左对齐，带头像 + Agent 名（与左栏配置同步）+ 气泡内容
- 跟项目品牌色路线 C 一致：**只头像 + 名字用品牌色，气泡正文中性**，不要全 agent 都品牌色（喧宾夺主）
- 空态：居中灰字引导"改改左边配置，发条消息试试 X 的反应"

#### 6.3.2 输入区

- 底部 sticky，宽度撑满
- Textarea（自动高度，max ~6 行），Enter 发送 / Shift+Enter 换行
- 右下角发送按钮（icon `Send`），输入空 / 处理中时 disabled
- 发送行为（v0 mock）：
  1. 未选模型 → toast "请先选择模型"，不发送
  2. 已选模型 → push 用户消息 → 500ms 后追加 mock assistant 回复（带当前模型名）→ 滚动到底
  3. pending 期间显示 typing 三点动画

### 6.4 移动端 / 小屏（v0 不强制）

- 桌面优先（agent 配置是桌面场景）
- 小屏可考虑左栏折叠成抽屉，但 v0 可只保桌面布局，给 1024px 以上设计

---

## 7. Workspace 占位

路径：`/workspaces`

- Outlet 壳（`workspaces.tsx`）
- index 页（`workspaces/index.tsx`）：`PagePlaceholder` 组件，标题"工作空间"，描述"多 agent 协作环境，即将上线"

不画卡片不画列表，纯占位。等 Agent 模块跑通 + 后端齐了再做工作空间。

---

## 8. Sidebar 导航

### 8.1 nav.config 改动

新顺序：

| 顺序 | 标题 | path | icon | 状态 |
|---|---|---|---|---|
| 1 | 主页 | `/` | LayoutDashboard | 不变 |
| 2 | **工作空间** | `/workspaces` | **Layers** | **新增** |
| 3 | Agents | `/agents` | Bot | 不变（标题保持 "Agents"） |
| 4 | 知识库 | `/knowledge` | BookOpen | 不变 |
| 5 | 工具 | `/tools` | Wrench | 不变 |
| 6 | 模型 | `/models` | Cpu | 不变 |

**Workspace icon 用 `Layers`**（堆叠感，符合"招募一组 agent 协作"语义）。

---

## 9. 视觉规范引用

直接遵循项目已有规范（详见 CLAUDE.md / context.md / app.css）：

- **图标**：lucide-react 静态图标 / ldrs 动态 loader，**不写 SVG，不引第二套库**
- **品牌色**：`#2f6b53`，用 token `bg-brand` / `text-brand` / `bg-brand-subtle` / `border-brand-border` / `hover:bg-brand-hover`
- **激活/选中**：`bg-brand-subtle + text-brand`
- **hover**：中性灰，不用品牌色
- **可点卡片**：统一套 `card-interactive`（hover 边框转墨绿 + 阴影 + 上浮 1px）
- **Loader**：ldrs `l-ring`，品牌色，60vh 居中
- **空态**：虚线边框 + 灰色字 + 提示文案（参考 Knowledge / Tools 空态）
- **字号 / 间距**：跟 Knowledge / Models 模块对齐
- **shadcn 组件**：用项目已装的（Button / Card / Dialog / Tabs / Accordion / Slider / Select / Textarea / Input / Avatar / Badge / Tooltip / AlertDialog / Command / Popover），缺则 `npx shadcn@latest add` 在 `frontend/` 跑

---

## 10. 交互细节清单

### 10.1 列表页

- 点 Header「创建 Agent」→ 打开 `CreateAgentDialog`（无预选模板）
- 点模板池任一卡 → 打开 `CreateAgentDialog`（预选该模板）
- 点 Agent 卡片整体 → 跳 `/agents/$id`
- Agent 卡片三点 dropdown：
  - "编辑"：跳详情
  - "复制为新 Agent"：禁用 + tooltip "v1.5+"
  - "删除"：AlertDialog 二次确认 → 本地 state 移除

### 10.2 弹窗

- 模板选择：单选高亮（品牌色边框）
- 名字默认值随模板变化（用户可覆写）
- 创建按钮：模板未选 / 名字空 → disabled
- 点创建：push 到 mockAgents（local state）+ toast "已创建" + close + 跳详情页（v0 跳详情就好，等接 API 再做"创建后跳"）

### 10.3 详情页 - 配置栏

- 字段改动即时反映到 local state，右栏对话用最新 state
- 行为模板 badge hover：tooltip "行为模板创建时选定，不可改"
- 模型 Select 不选：保留可空状态，但发送对话时提示"请先选择模型"
- System Prompt 占位：清晰提示"留空也可对话（裸 LLM 体验）"
- 知识库 / 工具多选：v0 用 Command + Popover，输入搜索 + Checkbox 勾选

### 10.4 详情页 - 沙盒试运行栏

- 单一沙盒模式，无 tab 切换；消息纯内存，刷新 / 离开即清
- 发送：
  - 模型未选 → toast "请先选择模型"，不发送
  - 模型已选 → push 用户消息 + 模拟一条 mock assistant 回复（500ms 延迟 + typing 三点动画）
- 用户气泡 / Agent 气泡视觉区分明确（颜色 / 对齐 / 头像）

### 10.5 删除 / 危险操作

所有删除走 shadcn `AlertDialog` 二次确认，跟项目其他模块一致。

### 10.6 持久化（v0 简化）

- 列表页 mockAgents：用一个 zustand mock store（`agent-mock-store.ts`）承载，列表页 / 详情页共用；纯内存，刷新还原初始 mock
- 沙盒消息：纯内存（刷新 / 离开即清），简单
- 想更好体验：用 zustand persist middleware 存 localStorage（不强求 v0 做）

---

## 11. 实施分批建议

按"每批独立可跑、可截图、有意义"原则切三批：

### 批次 1 — 基建占位（~30 min）

目标：导航和路由结构换成新形态，但内容都先占位。

- nav.config.ts：加 Workspace 项
- routes/_authenticated/workspaces.tsx + workspaces/index.tsx：占位
- types/agent.ts：重写（Template / Agent）
- types/index.ts：同步
- pages/agents/mock.ts：重写（先写模板池 + 几个 Agent，不写消息）

**完成标志**：能跑起来，sidebar 多了 Workspace 项，`/workspaces` 显示占位，`/agents` 列表页可能因为 mock 改动暂时报错或显示旧形态——这批主要目的是把数据/结构换掉。

### 批次 2 — 列表页 + 卡片 + 弹窗（~1 小时）

目标：Agents 列表页换成三带式，能创建（mock）。

- pages/agents/AgentCard.tsx：改造
- pages/agents/TemplateCard.tsx：新建
- pages/agents/AgentsPage.tsx：重写三带式
- pages/agents/CreateAgentDialog.tsx：新建

**完成标志**：访问 `/agents`，看到三带式布局，能点模板、能点创建按钮、弹窗能选模板起名、点创建后 toast + 加进列表。点单卡片暂时跳到 detail（详情页还是 placeholder）。

### 批次 3 — 详情页骨架（~1.5 小时）

目标：详情页左配右聊跑通。

- pages/agents/agent-mock-store.ts：新建（列表 / 详情共用）
- pages/agents/ConfigPanel.tsx：新建（左栏配置，方案 A 无框 + divider 分段）
- pages/agents/Playground.tsx：新建（右栏单一沙盒）
- pages/agents/AgentDetailPage.tsx：组装（左 40 / 右 60）
- routes/_authenticated/agents/$agentId.tsx：从 PagePlaceholder 升级

**完成标志**：从列表点进 Agent 详情，左边能改配置（即时落 store），右边沙盒能发消息收 mock 回复。

### 各批次共同的"完成 = 验收点"

- 类型检查 `npx tsc --noEmit` 通过
- 无 console error
- 截图能跟主 spec 的布局图对得上

---

## 附录 A：跟主 spec 的对应表

| 前端组件 / 文件 | 主 spec 章节 | 说明 |
|---|---|---|
| `AgentsPage.tsx` 三带式 | §4.1 | 列表页布局 |
| `TemplateCard.tsx` | §3.2 / §4.1 第二带 | 模板池只读展示 |
| `AgentCard.tsx` | §3.3 / §4.1 第三带 | 用户 Agent 卡片 |
| `CreateAgentDialog.tsx` | §3.3 | 创建 Agent（选模板 + 起名） |
| `AgentDetailPage.tsx` | §4.2 / §4.3 | 左配 40 + 右沙盒 60 |
| `ConfigPanel.tsx` 字段顺序 | §4.2 字段顺序 | 严格对齐 |
| `Playground.tsx` 单一沙盒 | §4.3 | 仅试运行，正式对话归 workspace |
| `nav.config.ts` | §2.1 | Sidebar 布局 |
| `workspaces/*` 占位 | §5 / §11 切片大纲 | 等切片 4+ 实施 |

---

## 附录 B：v0 → v1 切换点

后端齐了之后，把以下 mock 换成 API 调用，组件结构不动：

1. `pages/agents/mock.ts` 删除（替换成 `api/agent.ts` 调用）
2. 列表页 `useState` 改 `useEffect` + fetch
3. 创建 Agent 改成 POST 接口
4. Agent 详情页配置保存：现在是 local state，改成 debounced PATCH
5. 对话发送：现在是 mock 假回复，改成 SSE 流式接 LLM

**前端组件 / 视觉 / 交互一行不改**。这是分层架构的好处：UI 层跟数据源解耦。

---

## 维护规则

- 这份文档随主 spec 演进而更新
- 实施期间发现描述跟实际画法不符 → **以实际为准，回头更新本文档**
- 不要让文档跟代码长期不一致
