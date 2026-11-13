/** /chat/:agentId/c/:conversationId —— 单 Agent 的一条已有会话 */
import { createFileRoute } from '@tanstack/react-router'

import { AgentChat } from '@/pages/agent-chat/AgentChat'
import { useAgentSession } from '@/stores/agent-session'

export const Route = createFileRoute('/_authenticated/chat/$agentId/c/$conversationId')({
  component: AgentConversationRoute,
})

function AgentConversationRoute() {
  const { agentId, conversationId } = Route.useParams()
  const agent = useAgentSession((s) => s.agents.find((a) => a.id === agentId))
  if (!agent) return null
  // key=conversationId：切会话整块重挂（从 registry 取对应桶 / 重新拉历史）
  return (
    <AgentChat
      key={conversationId}
      agentId={agentId}
      agentName={agent.name}
      conversationId={conversationId}
      usable={agent.usable}
    />
  )
}
