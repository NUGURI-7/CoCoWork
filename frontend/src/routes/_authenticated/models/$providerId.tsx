/** /models/:providerId — Provider 详情页 */
import { createFileRoute } from '@tanstack/react-router'
import { Cpu } from 'lucide-react'
import ProviderDetailPage from '@/pages/models/ProviderDetailPage'

export const Route = createFileRoute('/_authenticated/models/$providerId')({
  staticData: { tabTitle: '供应商', tabIcon: Cpu },
  component: ProviderDetailPage,
})
