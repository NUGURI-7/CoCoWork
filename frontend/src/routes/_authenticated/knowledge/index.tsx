/** /knowledge — 知识库列表页 */
import { createFileRoute } from '@tanstack/react-router'
import { BookOpen } from 'lucide-react'
import KnowledgePage from '@/pages/knowledge/KnowledgePage'

export const Route = createFileRoute('/_authenticated/knowledge/')({
  staticData: { tabTitle: '知识库', tabIcon: BookOpen },
  component: KnowledgePage,
})
