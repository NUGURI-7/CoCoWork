/** /chat/:agentId/new —— 新对话：网址不带会话 id，发出第一句话后换成 /c/:conversationId */
import { useCallback, useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { v4 as uuidv4 } from 'uuid'
import { z } from 'zod'

import { AgentChat } from '@/pages/agent-chat/AgentChat'
import { useAgentSession } from '@/stores/agent-session'

/** ?q= 是官网体验链接带来的示例问题，预填进输入框、不自动发送 */
const searchSchema = z.object({
  q: z.string().optional(),
})

export const Route = createFileRoute('/_authenticated/chat/$agentId/new')({
  validateSearch: searchSchema,
  component: NewAgentConversationRoute,
})

function NewAgentConversationRoute() {
  const { agentId } = Route.useParams()
  const { q } = Route.useSearch()
  // 换 Agent 时整块重挂，拿一个新的会话 id
  return <NewAgentConversation key={agentId} agentId={agentId} initialText={q} />
}

function NewAgentConversation({ agentId, initialText }: { agentId: string; initialText?: string }) {
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
      initialText={initialText}
    />
  )
}
