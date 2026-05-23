/** admin 系统设置布局路由 — 左侧二级导航 + 右侧 Outlet */
import { createFileRoute } from '@tanstack/react-router'
import SettingsLayout from '@/pages/admin/SettingsLayout'

export const Route = createFileRoute('/admin/settings')({
  component: SettingsLayout,
})
