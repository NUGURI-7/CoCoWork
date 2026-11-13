/** /chat/:agentId/new —— 新对话：网址不带会话 id，发出第一句话后换成 /c/:conversationId */
import { useCallback, useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { v4 as uuidv4 } from 'uuid'

import { AgentChat } from '@/pages/agent-chat/AgentChat'
import { useAgentSession } from '@/stores/agent-session'

export const Route = createFileRoute('/_authenticated/chat/$agentId/new')({
  component: NewAgentConversationRoute,
})

function NewAgentConversationRoute() {
  const { agentId } = Route.useParams()
  // 换 Agent 时整块重挂，拿一个新的会话 id
  return <NewAgentConversation key={agentId} agentId={agentId} />
}

function NewAgentConversation({ agentId }: { agentId: string }) {
  const navigate = useNavigate()
  const agent = useAgentSession((s) => s.agents.find((a) => a.id === agentId))
  // 会话 id 由前端生成；停留在本页期间不变，发出第一句话时后端用它建库
  const [conversationId] = useState(() => uuidv4())

  // 第一句话已发出：网址换成这条会话的地址（replace，不留 /new 这条历史）
  const handleStarted = useCallback(() => {
    navigate({
      to: '/chat/$agentId/c/$conversationId',
      params: { agentId, conversationId },
      replace: true,
    })
  }, [navigate, agentId, conversationId])

  if (!agent) return null
  return (
    <AgentChat
      agentId={agentId}
      agentName={agent.name}
      conversationId={conversationId}
      isNew
      onStarted={handleStarted}
      usable={agent.usable}
    />
  )
}
