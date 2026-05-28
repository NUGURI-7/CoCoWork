import { createFileRoute } from '@tanstack/react-router'
import { LayoutDashboard } from 'lucide-react'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/admin/')({
  staticData: { tabTitle: '概览', tabIcon: LayoutDashboard },
  component: () => <PagePlaceholder title="管理后台" />,
})
