/** /chat/:agentId —— 单 Agent 对话页（员工直接使用一个 Agent） */
import { createFileRoute } from '@tanstack/react-router'
import { MessageSquare } from 'lucide-react'
import AgentChatPage from '@/pages/agent-chat/AgentChatPage'

export const Route = createFileRoute('/_authenticated/chat/$agentId')({
  staticData: { tabTitle: '对话', tabIcon: MessageSquare },
  component: AgentChatPage,
})
