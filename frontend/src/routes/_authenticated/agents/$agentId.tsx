/** /agents/:agentId — Agent 配置详情页（待实现） */
import { createFileRoute } from '@tanstack/react-router'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/_authenticated/agents/$agentId')({
  component: () => <PagePlaceholder title="Agent 配置" />,
})
