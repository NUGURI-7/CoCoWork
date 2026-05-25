/** /knowledge — 知识库列表页 */
import { createFileRoute } from '@tanstack/react-router'
import KnowledgePage from '@/pages/knowledge/KnowledgePage'

export const Route = createFileRoute('/_authenticated/knowledge/')({
  component: KnowledgePage,
})
