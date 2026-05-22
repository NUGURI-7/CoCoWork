import { createFileRoute } from '@tanstack/react-router'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/_authenticated/settings')({
  component: () => <PagePlaceholder title="设置" />,
})
