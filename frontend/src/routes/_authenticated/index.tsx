/** 主页 / —— 登录守卫由父级 _authenticated 统一处理 */
import { createFileRoute } from '@tanstack/react-router'
import HomePage from '@/pages/Home'

export const Route = createFileRoute('/_authenticated/')({
  component: HomePage,
})
