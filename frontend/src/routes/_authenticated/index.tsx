/** 主页 / —— 登录守卫由父级 _authenticated 统一处理 */
import { createFileRoute } from '@tanstack/react-router'
import { LayoutDashboard } from 'lucide-react'
import HomePage from '@/pages/Home'

export const Route = createFileRoute('/_authenticated/')({
  staticData: { tabTitle: '主页', tabIcon: LayoutDashboard },
  component: HomePage,
})
