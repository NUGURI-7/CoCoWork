import { createFileRoute } from '@tanstack/react-router'
import PagePlaceholder from '@/pages/PagePlaceholder'

export const Route = createFileRoute('/_authenticated/knowledge')({
  component: () => <PagePlaceholder title="知识库" />,
})
