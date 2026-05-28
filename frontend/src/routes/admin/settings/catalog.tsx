/** /admin/settings/catalog — 模型目录管理 */
import { createFileRoute } from '@tanstack/react-router'
import { Settings } from 'lucide-react'
import CatalogPage from '@/pages/admin/CatalogPage'

export const Route = createFileRoute('/admin/settings/catalog')({
  staticData: { tabTitle: '系统设置', tabIcon: Settings },
  component: CatalogPage,
})
