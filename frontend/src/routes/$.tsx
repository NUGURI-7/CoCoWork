/**
 * Catch-all 404 路由 — TanStack 的 splat 段命名是 `$`
 */

import { createFileRoute } from '@tanstack/react-router'
import NotFoundPage from '@/pages/NotFound'

export const Route = createFileRoute('/$')({
  component: NotFoundPage,
})
