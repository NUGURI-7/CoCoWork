/** /knowledge/:kbId — 知识库详情页 */
import { createFileRoute } from '@tanstack/react-router'
import { BookOpen } from 'lucide-react'
import KnowledgeDetailPage from '@/pages/knowledge/KnowledgeDetailPage'

export const Route = createFileRoute('/_authenticated/knowledge/$kbId')({
  staticData: { tabTitle: '知识库', tabIcon: BookOpen },
  component: KnowledgeDetailPage,
})
