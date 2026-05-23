/** /models/:providerId — Provider 详情页 */
import { createFileRoute } from '@tanstack/react-router'
import ProviderDetailPage from '@/pages/models/ProviderDetailPage'

export const Route = createFileRoute('/_authenticated/models/$providerId')({
  component: ProviderDetailPage,
})
