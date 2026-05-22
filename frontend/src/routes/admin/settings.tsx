import { createFileRoute } from '@tanstack/react-router'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/admin/settings')({
  component: () => <PagePlaceholder title="系统设置" />,
})
