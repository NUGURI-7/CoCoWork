/** /models — Provider 卡片主页 */
import { createFileRoute } from '@tanstack/react-router'
import ModelsPage from '@/pages/models/ModelsPage'

export const Route = createFileRoute('/_authenticated/models/')({
  component: ModelsPage,
})
