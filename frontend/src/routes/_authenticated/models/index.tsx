/** /models — Provider 卡片主页 */
import { createFileRoute } from '@tanstack/react-router'
import { Cpu } from 'lucide-react'
import ModelsPage from '@/pages/models/ModelsPage'

export const Route = createFileRoute('/_authenticated/models/')({
  staticData: { tabTitle: '模型', tabIcon: Cpu },
  component: ModelsPage,
})
