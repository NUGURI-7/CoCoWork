import { createFileRoute } from '@tanstack/react-router'
import { Layers } from 'lucide-react'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/_authenticated/workspaces/')({
  staticData: { tabTitle: '工作空间', tabIcon: Layers },
  component: () => (
    <PagePlaceholder
      title="工作空间"
      description="多 agent 协作环境，即将上线"
    />
  ),
})
