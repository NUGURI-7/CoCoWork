/**
 * 根路由 — 全局 layout
 *  - <Outlet /> 渲染子路由
 *  - <Toaster /> 全局 toast
 *  - 路由切换时的 nprogress 进度条由 main.tsx 的 router.subscribe 接管
 */

import { createRootRoute, Outlet } from '@tanstack/react-router'
import { Toaster } from '@/components/ui/sonner'

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return (
    <>
      <Outlet />
      <Toaster position="top-right" duration={3500} closeButton richColors />
    </>
  )
}
