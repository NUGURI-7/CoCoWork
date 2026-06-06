// ==================== SSE 事件 Payload ====================

export interface MessageStartPayload {
  conversation_uuid: string
  message_uuid: string
  model: string
  provider: string
}

export interface ContentBlockStartPayload {
  index: number
  type: 'text' // P1 加 'thinking'
}

export interface ContentBlockDeltaPayload {
  index: number
  type: 'text_delta'
  text: string
}

export interface ContentBlockStopPayload {
  index: number
}

export interface UsageInfo {
  input_tokens: number
  output_tokens: number
  image_count?: number
  cost: number | null
}

export interface MessageDeltaPayload {
  stop_reason: 'end_turn' | 'max_tokens' | 'cancelled'
  usage: UsageInfo
}

export interface SSEErrorPayload {
  code: string
  message: string
}

// ==================== DB / API Content Block ====================
// 这是存进后端 ChatMessage.content 字段、以及从详情接口回放的结构。
// 和渲染层的 RenderBlock 概念接近，但不带 UI 状态（status / index）。
export interface ApiTextBlock {
  type: 'text'
  text: string
}

export interface ApiToolUseBlock {
  type: 'tool_use'
  id: string
  name: string
  input: Record<string, unknown>
  status: 'success' | 'error'
  output: unknown
}

export interface ApiImageBlock {
  type: 'image'
  id: string
  status: 'ready' // 持久化层只存成功的
  url: string
}

export type ContentBlock = ApiTextBlock | ApiToolUseBlock | ApiImageBlock

// ==================== P1 Tool 事件 Payload ====================

export interface ToolUseStartPayload {
  index: number
  id: string
  name: string
  input_preview: string
}
export interface ToolUseStopPayload {
  index: number
  id: string
}

export interface ToolResultPayload {
  index: number
  id: string
  name: string
  status: 'success' | 'error'
  result_summary: string
  result_data: unknown
}

export interface ToolUseDeltaPayload {
  index: number
  id: string
  type: 'input_json_delta'
  partial_json: string
}

export interface ImageEventPayload {
  id: string
  status: 'loading' | 'ready' | 'error' | 'removed'
  url?: string
  message?: string
}

// ==================== 前端渲染状态 ====================

export interface TextBlock {
  type: 'text'
  index: number
  status: 'active' | 'done'
  content: string
}

export interface ToolUseBlock {
  type: 'tool_use'
  index: number
  status: 'building' | 'calling' | 'success' | 'error'
  id: string
  name: string
  inputPreview: string
  partialInputJson: string
  resultSummary: string | null
  resultData: unknown | null
  collapsed: boolean
}

export interface ImageBlock {
  type: 'image'
  index: number
  id: string
  status: 'loading' | 'ready' | 'error'
  url: string | null
  errorMessage: string | null
}

export type RenderBlock = TextBlock | ToolUseBlock | ImageBlock

export interface AssistantMessage {
  role: 'assistant'
  uuid: string
  model: string
  provider: string
  status: 'streaming' | 'completed' | 'error'
  blocks: RenderBlock[]
  usage: UsageInfo | null
  stopReason: string | null
  errorMessage: string | null
}

export interface UserMessage {
  role: 'user'
  uuid: string
  content: string
}

export type ChatMessage = UserMessage | AssistantMessage
