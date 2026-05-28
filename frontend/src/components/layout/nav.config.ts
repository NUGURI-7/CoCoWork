import { LayoutDashboard, Layers, Bot, BookOpen, Wrench, Cpu, type LucideIcon } from 'lucide-react'
import type { LinkProps } from '@tanstack/react-router'

export interface NavItem {
  title: string
  to: LinkProps['to']
  icon: LucideIcon
}

/** 侧边栏主导航 */
export const mainNav: NavItem[] = [
  { title: '主页', to: '/', icon: LayoutDashboard },
  { title: '工作空间', to: '/workspaces', icon: Layers },
  { title: 'Agents', to: '/agents', icon: Bot },
  { title: '知识库', to: '/knowledge', icon: BookOpen },
  { title: '工具', to: '/tools', icon: Wrench },
  { title: '模型', to: '/models', icon: Cpu },
]
