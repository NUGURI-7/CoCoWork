import { createFileRoute } from '@tanstack/react-router'
import { Settings } from 'lucide-react'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/_authenticated/settings')({
  staticData: { tabTitle: '设置', tabIcon: Settings },
  component: () => <PagePlaceholder title="设置" />,
})
