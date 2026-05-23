/** /admin/settings/catalog — 模型目录管理 */
import { createFileRoute } from '@tanstack/react-router'
import CatalogPage from '@/pages/admin/CatalogPage'

export const Route = createFileRoute('/admin/settings/catalog')({
  component: CatalogPage,
})
