/** /admin/settings — 默认跳转到第一个设置项 */
import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/admin/settings/')({
  beforeLoad: () => {
    throw redirect({ to: '/admin/settings/catalog' })
  },
})
