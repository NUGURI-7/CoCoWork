/**
 * /register — 已登录用户访问会被重定向到 /
 */

import { createFileRoute, redirect } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/auth'
import RegisterPage from '@/pages/auth/Register'

export const Route = createFileRoute('/register')({
  beforeLoad: () => {
    if (useAuthStore.getState().isLoggedIn()) {
      throw redirect({ to: '/' })
    }
  },
  component: RegisterPage,
})
