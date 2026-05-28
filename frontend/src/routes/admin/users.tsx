import { createFileRoute } from '@tanstack/react-router'
import { Users } from 'lucide-react'
import UsersPage from '@/pages/admin/UsersPage'

export const Route = createFileRoute('/admin/users')({
  staticData: { tabTitle: '用户管理', tabIcon: Users },
  component: UsersPage,
})
