/** /workspaces — 工作空间列表主页 */
import { createFileRoute } from '@tanstack/react-router'
import { Layers } from 'lucide-react'
import WorkspacesPage from '@/pages/workspaces/WorkspacesPage'

export const Route = createFileRoute('/_authenticated/workspaces/')({
  staticData: { tabTitle: '工作空间', tabIcon: Layers },
  component: WorkspacesPage,
})
