/** /agents/:agentId — Agent 配置详情页 */
import { createFileRoute } from '@tanstack/react-router'
import { Bot } from 'lucide-react'
import AgentDetailPage from '@/pages/agents/AgentDetailPage'

export const Route = createFileRoute('/_authenticated/agents/$agentId')({
  staticData: { tabTitle: 'Agent', tabIcon: Bot },
  component: AgentDetailPage,
})
