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
}

// ============ SSE Event Payload ============
// 跟 backend/app/agents/runtime/adapter.py 发的 11 个事件 data 一对一。

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

export interface MessageDeltaPayload {
  /** 'end_turn' / 'tool_use' / 'max_tokens' / 'cancelled' 等；后端宽松 string，前端也宽松 */
  stop_reason: string
  usage: Usage
}

export interface ContentBlockStartPayload {
  index: number
  type: 'text' | 'thinking'
}

export interface ContentBlockDeltaPayload {
  index: number
  type: 'text_delta' | 'thinking_delta'
  /** type=text_delta 时携带 */
  text?: string
  /** type=thinking_delta 时携带 */
  thinking?: string
}

export interface ContentBlockStopPayload {
  index: number
}

export interface ToolUseStartPayload {
  index: number
  id: string
  name: string
  input_preview: string
}

export interface ToolUseDeltaPayload {
  index: number
  id: string
  type: 'input_json_delta'
  partial_json: string
}

export interface ToolUseStopPayload {
  index: number
  id: string
}

export interface ToolResultPayload {
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

export type RenderBlock = TextBlock | ThinkingBlock | ToolUseBlock

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
}

export type ChatMessage = UserMessage | AssistantMessage
