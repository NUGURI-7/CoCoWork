/**
 * /login — 已登录用户访问会被重定向到 /
 *
 * search 参数 ?redirect=... 用于登录后跳回原页面。
 */

import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { useAuthStore } from '@/stores/auth'
import LoginPage from '@/pages/auth/Login'

const loginSearchSchema = z.object({
  redirect: z.string().optional(),
})

export const Route = createFileRoute('/login')({
  validateSearch: loginSearchSchema,
  beforeLoad: () => {
    if (useAuthStore.getState().isLoggedIn()) {
      throw redirect({ to: '/' })
    }
  },
  component: LoginPage,
})
