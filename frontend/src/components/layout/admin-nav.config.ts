import { LayoutDashboard, Users, Settings, type LucideIcon } from 'lucide-react'
import type { LinkProps } from '@tanstack/react-router'

export interface AdminNavItem {
  title: string
  to: LinkProps['to']
  icon: LucideIcon
}

export const adminNav: AdminNavItem[] = [
  { title: '概览', to: '/admin', icon: LayoutDashboard },
  { title: '用户管理', to: '/admin/users', icon: Users },
  { title: '系统设置', to: '/admin/settings', icon: Settings },
]
