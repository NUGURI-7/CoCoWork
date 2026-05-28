/** /workspaces/:workspaceId — 工作空间详情页 */
import { createFileRoute } from '@tanstack/react-router'
import { Layers } from 'lucide-react'
import WorkspaceDetailPage from '@/pages/workspaces/WorkspaceDetailPage'

export const Route = createFileRoute('/_authenticated/workspaces/$workspaceId')({
  staticData: { tabTitle: '工作空间', tabIcon: Layers },
  component: WorkspaceDetailPage,
})
