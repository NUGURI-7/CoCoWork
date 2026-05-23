import { Library, type LucideIcon } from 'lucide-react'
import type { LinkProps } from '@tanstack/react-router'

export interface SettingsNavItem {
  title: string
  to: LinkProps['to']
  icon: LucideIcon
}

/** admin 系统设置内的二级导航。新增设置项往这里加。 */
export const settingsNav: SettingsNavItem[] = [
  { title: '模型目录', to: '/admin/settings/catalog', icon: Library },
]
