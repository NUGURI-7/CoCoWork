/** 模型模块布局路由 — 子页面通过 <Outlet /> 切换 */
import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/models')({
  component: () => <Outlet />,
})
