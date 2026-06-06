# Windify — 流式渲染规范

> SSE 事件协议、前端状态机、块类型与组件映射的完整定义。
> 最后更新：2026-03-26

---

## 1. 设计原则

1. **从 P0 起使用结构化事件协议**：P0 只发文本相关事件，P1/P2 增量添加新事件类型，前端只需新增 listener，不重构已有逻辑。
2. **事件级块渲染**：前端不是拼接一个大字符串，而是根据 SSE 事件类型实时创建、更新、关闭独立的渲染块（Block）。
3. **零额外静态资源**：所有视觉区分通过 Phosphor Icons + Tailwind CSS 类名 + CSS 动画实现，不引入图片或自定义 SVG。

---

## 2. SSE 事件协议

### 2.1 通用格式

```
event: <event_type>
data: <JSON payload>

```

每个事件由 `event` 行 + `data` 行组成，事件之间以空行分隔。前端通过 `EventSource` 或 `fetch` + `ReadableStream` 消费。

### 2.2 完整事件类型表

| 事件类型 | 引入阶段 | 方向 | 说明 |
|----------|----------|------|------|
| `message_start` | P0 | 开始 | 一轮 AI 回复的起点，携带元信息 |
| `content_block_start` | P0 | 开始 | 一个内容块开始（text / thinking） |
| `content_block_delta` | P0 | 增量 | 内容块的增量数据（逐 token 文字） |
| `content_block_stop` | P0 | 结束 | 一个内容块结束 |
| `tool_use_start` | P1 | 开始 | Agent 开始调用一个 Tool |
| `tool_use_delta` | P1 | 增量 | Tool 输入参数的增量流（可选） |
| `tool_use_stop` | P1 | 结束 | Tool 调用参数构建完成 |
| `tool_result` | P1 | 数据 | Tool 执行结果返回 |
| `message_delta` | P0 | 元数据 | 回复即将结束，携带 stop_reason 和 usage |
| `message_stop` | P0 | 结束 | 一轮回复完全结束 |
| `error` | P0 | 错误 | 异常中断 |

### 2.3 各事件的 Payload 定义

#### `message_start`

```json
{
  "conversation_uuid": "550e8400-...",
  "message_uuid": "6ba7b810-...",
  "model": "deepseek-chat",
  "provider": "deepseek"
}
```

#### `content_block_start`

```json
{
  "index": 0,
  "type": "text"
}
```

`type` 取值：
- `"text"` — 正文文本（P0）
- `"thinking"` — 推理/思考过程（P1，DeepSeek-R1 等支持 thinking 的模型）

#### `content_block_delta`

```json
{
  "index": 0,
  "type": "text_delta",
  "text": "你好"
}
```

对于 `thinking` 类型块：

```json
{
  "index": 0,
  "type": "thinking_delta",
  "thinking": "让我分析一下..."
}
```

#### `content_block_stop`

```json
{
  "index": 0
}
```

#### `tool_use_start`（P1）

```json
{
  "index": 1,
  "tool_call_id": "call_abc123",
  "tool_name": "web_search",
  "tool_display_name": "搜索网页",
  "tool_input_preview": "PydanticAI streaming tutorial"
}
```

#### `tool_use_delta`（P1，可选）

```json
{
  "index": 1,
  "type": "input_json_delta",
  "partial_json": "{\"query\": \"Pydan"
}
```

> 大多数情况下 Tool 输入较短，不需要流式传输。此事件为可选项，用于大 JSON 输入的场景。

#### `tool_use_stop`（P1）

```json
{
  "index": 1,
  "tool_call_id": "call_abc123"
}
```

#### `tool_result`（P1）

```json
{
  "index": 1,
  "tool_call_id": "call_abc123",
  "tool_name": "web_search",
  "status": "success",
  "result_summary": "找到 5 条相关结果",
  "result_data": { ... }
}
```

`status` 取值：`"success"` | `"error"`

#### `message_delta`

```json
{
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 120,
    "output_tokens": 58,
    "total_tokens": 178,
    "cost": 0.0001
  }
}
```

`stop_reason` 取值：`"end_turn"` | `"tool_use"` | `"max_tokens"` | `"cancelled"`

#### `message_stop`

```json
{}
```

#### `error`

```json
{
  "code": "provider_error",
  "message": "DeepSeek API rate limit exceeded"
}
```

`code` 取值：`"provider_error"` | `"context_overflow"` | `"cancelled"` | `"internal_error"`

---

## 3. 前端状态机

### 3.1 消息级状态

一条 AI 回复消息（`AssistantMessage`）从 `message_start` 到 `message_stop` 经历以下状态：

```
idle → streaming → completed
                 → error
```

```ts
interface AssistantMessage {
  uuid: string
  model: string
  provider: string
  status: 'streaming' | 'completed' | 'error'
  blocks: RenderBlock[]
  usage: Usage | null
  stopReason: string | null
}
```

### 3.2 块级状态

每个 `RenderBlock` 有独立的生命周期：

```
pending → active → done
                 → error
```

```ts
type RenderBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock

interface TextBlock {
  type: 'text'
  index: number
  status: 'active' | 'done'
  content: string          // 持续拼接 delta
}

interface ThinkingBlock {
  type: 'thinking'
  index: number
  status: 'active' | 'done'
  content: string
  collapsed: boolean       // 用户可折叠，默认 true（完成后折叠）
}

interface ToolUseBlock {
  type: 'tool_use'
  index: number
  status: 'calling' | 'success' | 'error'
  toolCallId: string
  toolName: string
  toolDisplayName: string
  inputPreview: string
  resultSummary: string | null
  resultData: unknown | null
  collapsed: boolean       // 用户可折叠，默认 false（展开显示结果）
}
```

### 3.3 事件分发逻辑

```ts
function handleSSEEvent(event: MessageEvent, message: AssistantMessage) {
  const data = JSON.parse(event.data)

  switch (event.type) {
    case 'message_start':
      // 初始化 AssistantMessage
      break

    case 'content_block_start':
      // 根据 data.type 创建新的 RenderBlock，push 到 message.blocks
      break

    case 'content_block_delta':
      // 找到 blocks[data.index]，追加 text/thinking 内容
      break

    case 'content_block_stop':
      // 找到 blocks[data.index]，标记 status = 'done'
      break

    case 'tool_use_start':
      // 创建 ToolUseBlock，status = 'calling'
      break

    case 'tool_result':
      // 找到对应 ToolUseBlock，填充结果，更新 status
      break

    case 'message_delta':
      // 更新 usage 和 stopReason
      break

    case 'message_stop':
      // message.status = 'completed'
      break

    case 'error':
      // message.status = 'error'
      break
  }
}
```

---

## 4. 块类型 → 组件 → 视觉映射

### 4.1 P0 组件（文本流）

| 块类型 | Vue 组件 | 视觉处理 |
|--------|----------|----------|
| `text` (active) | `<TextBlock>` | Markdown 渲染 + 末尾闪烁光标 `▊` |
| `text` (done) | `<TextBlock>` | 纯 Markdown 渲染，光标消失 |

**闪烁光标实现**：

```css
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.streaming-cursor::after {
  content: '▊';
  animation: cursor-blink 1s step-end infinite;
  color: var(--foreground);
  opacity: 0.7;
}
```

### 4.2 P1 组件（Tool 调用 + 思考）

| 块类型 | Vue 组件 | 视觉处理 |
|--------|----------|----------|
| `thinking` (active) | `<ThinkingBlock>` | 可折叠卡片，`bg-muted/50 rounded-lg border border-border/50 p-3`，内容渐显 |
| `thinking` (done) | `<ThinkingBlock>` | 同上，默认折叠，点击展开 |
| `tool_use` (calling) | `<ToolUseBlock>` | 卡片 + 旋转图标 + 工具名 + 输入预览 |
| `tool_use` (success) | `<ToolUseBlock>` | 卡片 + 成功图标 + 结果摘要，可折叠展开完整结果 |
| `tool_use` (error) | `<ToolUseBlock>` | 卡片 + 错误图标 + 错误信息 |

### 4.3 图标映射（全部来自 `@phosphor-icons/vue`）

| 场景 | 图标 | Tailwind 类 |
|------|------|-------------|
| 流式光标 | 无（CSS `::after` 伪元素） | — |
| 思考中 | `PhBrain` | `text-muted-foreground animate-pulse` |
| 思考完成 | `PhBrain` | `text-muted-foreground` |
| Tool 调用中 | `PhCircleNotch` | `text-primary animate-spin` |
| Tool 成功 | `PhCheckCircle` | `text-success` |
| Tool 失败 | `PhWarningCircle` | `text-destructive` |
| Web 搜索 Tool | `PhGlobe` | — |
| Notes 搜索 Tool | `PhNotePencil` | — |
| RAG 检索 Tool | `PhDatabase` | — |
| 代码执行 Tool | `PhTerminal` | — |
| 错误消息 | `PhWarning` | `text-destructive` |
| 复制代码 | `PhCopy` / `PhCheck` | — |

### 4.4 Tool 卡片布局

```
┌─────────────────────────────────────────┐
│ [🔄 PhCircleNotch]  搜索网页            │  ← 图标 + 工具显示名
│                                         │
│  查询: "PydanticAI streaming tutorial"  │  ← 输入预览（text-muted-foreground text-xs）
│                                         │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │  ← 分隔线（仅结果返回后出现）
│                                         │
│  找到 5 条相关结果                       │  ← 结果摘要
│  ▸ 展开完整结果                         │  ← 折叠/展开触发器
└─────────────────────────────────────────┘
```

Tailwind 类参考：

```
bg-muted/30 rounded-lg border border-border/50 p-3 space-y-2
```

---

## 5. Markdown 渲染

Chat 中的文本块需要渲染 Markdown。

### 5.1 方案选择

使用 `markdown-it`（或同等轻量库）+ 代码高亮插件，**不复用 Milkdown**（Milkdown 是编辑器，Chat 只需只读渲染）。

### 5.2 需要支持的 Markdown 元素

| 元素 | 优先级 | 说明 |
|------|--------|------|
| 段落、加粗、斜体、链接 | P0 | 基础文本 |
| 代码块（语法高亮） | P0 | AI 回复最常见的结构化内容 |
| 行内代码 | P0 | |
| 有序/无序列表 | P0 | |
| 标题（h1-h4） | P0 | |
| 表格 | P1 | |
| 引用块 | P1 | |
| 数学公式（KaTeX） | P2 | 按需引入 |

### 5.3 代码块增强

- 右上角复制按钮：`PhCopy` → 点击后变 `PhCheck`（1.5s 后恢复）
- 语言标签：左上角显示语言名
- 语法高亮：Shiki（与 Milkdown 保持一致）或 highlight.js

---

## 6. 错误处理

| 错误场景 | 前端行为 |
|----------|----------|
| SSE 连接断开 | 显示"连接中断"提示条，保留已渲染内容 |
| `error` 事件 | 消息状态标记为 error，末尾显示红色错误条 |
| Provider 限流 | 显示错误信息 + 建议切换模型 |
| Context 超长 | 显示错误信息 + 建议开新对话 |
| 网络超时 | 自动重试一次，失败后提示用户手动重试 |

错误条样式：

```
bg-destructive/10 text-destructive rounded-md p-3 text-sm
[PhWarning :size="14"]  错误信息文字
```

---

## 7. 持久化与回放

### 7.1 存储格式

AI 回复完成后（`message_stop`），将 `AssistantMessage` 序列化为 `ChatMessage.content`：

```json
{
  "blocks": [
    {
      "type": "thinking",
      "content": "让我分析一下这个问题..."
    },
    {
      "type": "tool_use",
      "tool_name": "web_search",
      "tool_display_name": "搜索网页",
      "input_preview": "PydanticAI tutorial",
      "status": "success",
      "result_summary": "找到 5 条结果",
      "result_data": { ... }
    },
    {
      "type": "text",
      "content": "根据搜索结果，PydanticAI 的流式输出..."
    }
  ]
}
```

### 7.2 历史消息回放

加载历史对话时，直接从 JSON 反序列化为 `RenderBlock[]`，所有块 `status = 'done'`，无需重放 SSE 事件流。

---

## 8. 阶段实施对照

| 阶段 | 后端事件 | 前端组件 | 块类型 |
|------|----------|----------|--------|
| **P0** | message_start, content_block_start/delta/stop, message_delta, message_stop, error | `<TextBlock>`, 闪烁光标, 错误条 | text |
| **P1** | + tool_use_start/delta/stop, tool_result | + `<ThinkingBlock>`, `<ToolUseBlock>` | + thinking, tool_use |
| **P2** | 无新事件类型（RAG Tool 复用 tool_use_*） | 无新组件（RAG Tool 复用 ToolUseBlock） | 无新类型 |

---

## 维护规则

- 新增 SSE 事件类型时，必须同时更新 §2（协议）、§3（状态机）、§4（组件映射）三个部分
- 本文档与实际代码保持同步，协议变更必须先更新文档再改代码
