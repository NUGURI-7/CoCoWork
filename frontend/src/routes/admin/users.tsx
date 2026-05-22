import { createFileRoute } from '@tanstack/react-router'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/admin/users')({
  component: () => <PagePlaceholder title="用户管理" />,
})
