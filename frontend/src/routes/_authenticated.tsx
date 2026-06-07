/**
 * 工作台布局（pathless layout）—— 所有需登录的页面都挂在它下面。
 *  - beforeLoad：登录守卫（从原 routes/index.tsx 上提，一处保护全部子页面）
 *  - component：渲染 AppShell（侧边栏 + 顶栏），子页面在 <Outlet /> 内切换
 *
 * 名字带下划线 = pathless：不占 URL 段（/agents 而非 /_authenticated/agents）。
 */

import { createFileRoute, redirect, Outlet } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/auth'
import { AppShell } from '@/components/layout/AppShell'

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ location }) => {
    const auth = useAuthStore.getState()
    // token 已过期：清状态再走未登录分支跳登录页（防系统休眠睡过头 / 改系统时间）
    if (auth.isLoggedIn() && auth.isExpired()) {
      auth.logout()
    }
    if (!auth.isLoggedIn()) {
      throw redirect({ to: '/login', search: { redirect: location.href } })
    }
    if (auth.token && !auth.user) {
      try {
        await auth.fetchMe()
      } catch {
        /* 401 由 request 拦截器处理跳转 */
      }
    }
  },
  component: AuthenticatedLayout,
})

function AuthenticatedLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}
