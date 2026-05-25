/** /knowledge/:kbId — 知识库详情页 */
import { createFileRoute } from '@tanstack/react-router'
import KnowledgeDetailPage from '@/pages/knowledge/KnowledgeDetailPage'

export const Route = createFileRoute('/_authenticated/knowledge/$kbId')({
  component: KnowledgeDetailPage,
})
