/**
 * 首页 / — 需要登录
 *
 * beforeLoad 守卫：
 *  - 未登录 → redirect /login，带 search.redirect=/ 登录后跳回
 *  - 已登录但 user=null（刷新后场景） → 调 fetchMe()；失败由 401 拦截器处理
 */

import { createFileRoute, redirect } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/auth'
import HomePage from '@/pages/Home'

export const Route = createFileRoute('/')({
  beforeLoad: async ({ location }) => {
    const auth = useAuthStore.getState()
    if (!auth.isLoggedIn()) {
      throw redirect({ to: '/login', search: { redirect: location.href } })
    }
    if (auth.token && !auth.user) {
      try {
        await auth.fetchMe()
      } catch {
        /* 拦截器已处理跳转 */
      }
    }
  },
  component: HomePage,
})
