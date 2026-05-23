/** /agents — Agent 列表主页 */
import { createFileRoute } from '@tanstack/react-router'
import AgentsPage from '@/pages/agents/AgentsPage'

export const Route = createFileRoute('/_authenticated/agents/')({
  component: AgentsPage,
})
