/** /agents — Agent 列表主页 */
import { createFileRoute } from '@tanstack/react-router'
import { Bot } from 'lucide-react'
import AgentsPage from '@/pages/agents/AgentsPage'

export const Route = createFileRoute('/_authenticated/agents/')({
  staticData: { tabTitle: 'Agents', tabIcon: Bot },
  component: AgentsPage,
})
