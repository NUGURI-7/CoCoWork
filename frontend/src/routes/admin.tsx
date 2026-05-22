import { createFileRoute, redirect, Outlet } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/auth'
import { AdminShell } from '@/components/layout/AdminShell'

export const Route = createFileRoute('/admin')({
  beforeLoad: async ({ location }) => {
    const auth = useAuthStore.getState()
    if (!auth.isLoggedIn()) {
      throw redirect({ to: '/login', search: { redirect: location.href } })
    }
    if (auth.token && !auth.user) {
      try {
        await auth.fetchMe()
      } catch {
        return
      }
    }
    if (!useAuthStore.getState().isAdmin()) {
      throw redirect({ to: '/' })
    }
  },
  component: AdminLayout,
})

function AdminLayout() {
  return (
    <AdminShell>
      <Outlet />
    </AdminShell>
  )
}
