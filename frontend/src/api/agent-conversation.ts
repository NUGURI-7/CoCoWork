/**
 * 单 Agent 会话 API — 对接 backend/app/api/routes/agent/conversation.py
 * 以及侧栏选择器用的 GET /agents/available。
 *
 * 会话在发出第一句话时才由后端建，没有单独的「建会话」接口；会话 id 由前端生成。
 * 对话流（/stream）走 api/chat-stream.ts，endpoint 由调用方拼好注入。
 */
import { del, get, post, put } from '@/request'
import type {
  AgentBrief,
  AgentConversation,
  ConversationTitle,
  ConversationUpdatePayload,
  WorkspaceMessage,
} from '@/types'

/** 侧栏选择器：自己建的 + 管理员建的已启用的 + 管理员建的、自己聊过的（已下线）。 */
export function listAvailableAgents() {
  return get<AgentBrief[]>('/agents/available')
}

/** 自己在这个 Agent 下的会话（后端按 updated_at 倒序）。 */
export function listAgentConversations(agentId: string) {
  return get<AgentConversation[]>(`/agents/${agentId}/conversations`)
}

/** 改名。 */
export function updateAgentConversation(
  agentId: string,
  conversationId: string,
  payload: ConversationUpdatePayload,
) {
  return put<AgentConversation>(`/agents/${agentId}/conversations/${conversationId}`, payload, {
    silent: true,
  })
}

/** 自动起名，与对话流并发发出；silent —— 失败静默，下次进对话再试。 */
export function generateAgentConversationTitle(
  agentId: string,
  conversationId: string,
  content: string,
) {
  return post<ConversationTitle>(
    `/agents/${agentId}/conversations/${conversationId}/generate-title`,
    { content },
    { silent: true },
  )
}

/** 删除会话（连带删消息）。 */
export function deleteAgentConversation(agentId: string, conversationId: string) {
  return del<null>(`/agents/${agentId}/conversations/${conversationId}`)
}

/** 会话历史（升序，老→新）。消息形态与工作空间一致，sender_kind 为 null。 */
export function listAgentMessages(agentId: string, conversationId: string) {
  return get<WorkspaceMessage[]>(`/agents/${agentId}/conversations/${conversationId}/messages`)
}

/** 拼对话流 SSE endpoint（路径相对 axios baseURL）。 */
export function agentConversationStreamEndpoint(agentId: string, conversationId: string): string {
  return `/agents/${agentId}/conversations/${conversationId}/stream`
}
