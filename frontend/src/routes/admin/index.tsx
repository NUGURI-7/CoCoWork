import { createFileRoute } from '@tanstack/react-router'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/admin/')({
  component: () => <PagePlaceholder title="管理后台" />,
})
