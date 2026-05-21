/**
 * Vue Router — 路由表 + 守卫 + nprogress
 *
 * 守卫策略：meta.requiresAuth / meta.guestOnly 二分
 * 持久化：token 在 localStorage，user 不持久化，刷新后守卫补 fetchMe
 */

import { createRouter, createWebHistory } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { useAuthStore } from '@/stores/auth'

NProgress.configure({ showSpinner: false, easing: 'ease', speed: 400 })

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/Home.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/Login.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/Register.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  NProgress.start()
  const auth = useAuthStore()

  // 刷新页面后 token 还在但 user 为空 → 补拉一次
  // 失败由 request 拦截器统一处理（清 token + 跳 /login），守卫这里只 catch 防卡死
  if (auth.token && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      /* 拦截器已处理跳转 */
    }
  }

  // 需要登录的页面但未登录 → /login，带 redirect 参数登录后跳回
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 已登录访问登录/注册页 → /
  if (to.meta.guestOnly && auth.isLoggedIn) {
    return { path: '/' }
  }
})

router.afterEach(() => {
  NProgress.done()
})

router.onError(() => {
  NProgress.done()
})

export default router

// =============================================================================
// meta 字段类型扩展 — 让 to.meta.requiresAuth / guestOnly 有类型提示
// =============================================================================
declare module 'vue-router' {
  interface RouteMeta {
    /** 需要登录才能访问 */
    requiresAuth?: boolean
    /** 仅未登录可访问（已登录跳 /） */
    guestOnly?: boolean
  }
}
