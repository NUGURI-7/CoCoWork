/**
 * 通用对话契约 —— Playground / Workspace 共用。
 *
 * 镜像后端 `app/schemas/agent/chat_schema.py` + `app/agents/runtime/adapter.py` 的事件协议。
 * 不绑场景，任何 SSE 流式对话能力都通过这一份类型流转。
 *
 * 三层结构：
 * 1. 协议层（Api*）—— 跟后端字段 100% 一致，作为 HTTP / SSE 传输契约
 * 2. SSE event payload —— 跟 adapter 发的 11 个事件 data 一对一
 * 3. 渲染层（RenderBlock + AssistantMessage）—— 带 UI 状态（status / collapsed），store 维护
 *
 * 命名约定：
 * - API payload / 协议层字段：snake_case（直接透传后端，零字段映射）
 * - 前端内部状态字段：camelCase（React 惯例）
 * - usage 子对象内部：snake_case（透传 payload.usage，不做字段映射）
 */

// ============ 协议层（HTTP / SSE 传输契约，snake_case） ============

export interface ApiTextBlock {
  type: 'text'
  text: string
}

/**
 * P0 union 只有 TextBlock；P1 加 ApiToolUseBlock / ApiImageBlock 时这里扩。
 * 加 union 成员不破坏上层（discriminator: type）。
 */
export type ApiContentBlock = ApiTextBlock

export interface ApiHistoryMessage {
  role: 'user' | 'assistant'
  content: ApiContentBlock[]
}

/** POST body —— 沙盒不入库，前端持 history 整段送回。 */
export interface ChatStreamRequest {
  content: ApiContentBlock[]
  history: ApiHistoryMessage[]
  /** 被 @ 的成员 id（WorkspaceMember.id）。仅 workspace @直连用；
   *  Playground / supervisor 不传，JSON.stringify 自动省略 undefined。 */
  mentioned_member_ids?: string[]
}

// ============ SSE Event Payload ============
// 跟 backend/app/agents/runtime/adapter.py 发的 11 个事件 data 一对一。

/**
 * 块事件的归属戳 —— adapter 主循环按 `metadata.lc_agent_name` 注入。
 * 来自被派活成员（子 agent）的块 = `member_xxx`；管家主流的块 = undefined。
 * dispatch 据此把块路由进对应派活块（DelegateBlock）还是主流。
 */
export interface SubagentScoped {
  subagent?: string
  /**
   * 归属哪次派活的戳 = 对应 task 工具的 tool_call_id（call_xxx）。adapter 主循环按
   * 泳道盖上。同名成员被并发派活时，靠它（而非成员名）把子块归进正确的派活卡片。
   */
  delegate_id?: string
}

export interface MessageStartPayload {
  id: string
  role: 'assistant'
}

export interface MessageStopPayload {
  id: string
}

export interface Usage {
  input_tokens: number
  output_tokens: number
}

export interface MessageDeltaPayload extends SubagentScoped {
  /** 'end_turn' / 'tool_use' / 'max_tokens' / 'cancelled' 等；后端宽松 string，前端也宽松 */
  stop_reason: string
  usage: Usage
}

export interface ContentBlockStartPayload extends SubagentScoped {
  index: number
  type: 'text' | 'thinking'
}

export interface ContentBlockDeltaPayload extends SubagentScoped {
  index: number
  type: 'text_delta' | 'thinking_delta'
  /** type=text_delta 时携带 */
  text?: string
  /** type=thinking_delta 时携带 */
  thinking?: string
}

export interface ContentBlockStopPayload extends SubagentScoped {
  index: number
}

export interface ToolUseStartPayload extends SubagentScoped {
  index: number
  id: string
  name: string
  input_preview: string
}

export interface ToolUseDeltaPayload extends SubagentScoped {
  index: number
  id: string
  type: 'input_json_delta'
  partial_json: string
}

export interface ToolUseStopPayload extends SubagentScoped {
  index: number
  id: string
}

export interface ToolResultPayload extends SubagentScoped {
  index: number
  id: string
  status: 'success' | 'error'
  result_summary: string
  result_data: unknown
}

export interface ErrorPayload {
  /** 'internal_error' / 'provider_error' / 'context_overflow' / 'cancelled' 等 */
  code: string
  message: string
}

/**
 * 沙箱产物 —— agent 这一轮交付给用户的一个文件。
 *
 * 「哪些算产物」由后端的交付区决定（每轮一个空目录，放进去的就是），
 * 前端不做任何判断，收到什么就渲染什么。
 *
 * **刻意不含下载 URL**：URL 在用户点击时才向后端换取（短期预签名），
 * 于是每次点击都过一遍归属校验，链接也不会长期有效。
 */
export interface Artifact {
  id: string
  filename: string
  /** 字节数 */
  size: number
  /** 后端按扩展名推出的 MIME，决定图标与「能不能直接看」 */
  content_type: string
}

export interface ArtifactsPayload {
  message_id: string
  artifacts: Artifact[]
}

// ============ 渲染层（RenderBlock + UI 状态，camelCase） ============

export interface TextBlock {
  type: 'text'
  index: number
  status: 'active' | 'done'
  content: string
}

export interface ThinkingBlock {
  type: 'thinking'
  index: number
  status: 'active' | 'done'
  content: string
  /** active 期默认展开、done 后默认折叠 */
  collapsed: boolean
}

export interface ToolUseBlock {
  type: 'tool_use'
  index: number
  /**
   * building — 收到 tool_use_start、还在收 partial_json
   * calling  — tool_use_stop 收齐参数、等待执行
   * success  — tool_result 返成功
   * error    — tool_result 返错误
   */
  status: 'building' | 'calling' | 'success' | 'error'
  id: string
  name: string
  inputPreview: string
  partialInputJson: string
  resultSummary: string | null
  resultData: unknown
  collapsed: boolean
}

/**
 * 派活块 —— 管家调 `task` 工具把活分给某成员（子 agent）时建。
 *
 * 它在主流 blocks 里占位（管家「我让老二算」的位置），自己内部嵌一个 `blocks`
 * 装子 agent 实时干活的块；渲染成可折叠块（块头成员标识 + 展开看执行过程）。
 *
 * - index        = task 工具块的全局块编号
 * - subagentName = 派给谁（member_xxx，与后端块事件的 subagent 戳一致）
 * - task         = 派的活（task 工具的 description 参数）
 * - blocks       = 子 agent 的实时块（不会再嵌 delegate —— 子 agent 没有 task 工具）
 */
export interface DelegateBlock {
  type: 'delegate'
  index: number
  /** 本次 task 工具的 tool_call_id（call_xxx）；子块靠 delegate_id 与它匹配来归卡片 */
  callId: string
  status: 'running' | 'done' | 'error'
  subagentName: string
  task: string
  blocks: RenderBlock[]
  collapsed: boolean
  /** 累积 task 工具的流式 args（partial JSON）；tool_use_stop 时解析出 subagentName + task */
  argsJson: string
}

export type RenderBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock
  | DelegateBlock

// ============ Message（user / assistant union） ============

export interface UserMessage {
  role: 'user'
  /** 前端生成的 UUID，给 React key / 滚动定位用 */
  id: string
  content: ApiContentBlock[]
}

export interface AssistantMessage {
  role: 'assistant'
  /** 后端 message_start 给的 message_id */
  id: string
  /** streaming — 流中、completed — 正常结束、error — 中断 */
  status: 'streaming' | 'completed' | 'error'
  blocks: RenderBlock[]
  /** message_delta 给的 token 计数；usage 内部保留 snake_case（透传） */
  usage: Usage | null
  /** message_delta 给的 stop_reason */
  stopReason: string | null
  /** error 事件给的 message（已脱敏） */
  errorMessage: string | null
  /**
   * 这一轮沙箱交付出来的文件。没挂 skill / 没产出时为 undefined。
   * 来自 artifacts 事件（在 message_stop 之前到）。
   */
  artifacts?: Artifact[]
  /**
   * @直连应答的成员 id（WorkspaceMember.id）。supervisor / Playground 应答为 undefined。
   * 实时：send 时记下被 @ 的成员、message_start 标上；回放：从 DB sender_member_id 译。
   * 渲染：MessageList 据此在气泡顶上显示成员头像 / 名字（查 SubagentDirectory）。
   */
  senderMemberId?: string
}

export type ChatMessage = UserMessage | AssistantMessage
