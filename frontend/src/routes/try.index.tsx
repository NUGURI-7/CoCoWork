/** /try —— 体验凭证过期后落到这里，引导访客回官网重新进入 */
import { createFileRoute } from '@tanstack/react-router'

import { DemoNotice } from '@/pages/demo/DemoNotice'

export const Route = createFileRoute('/try/')({
  component: () => (
    <DemoNotice title="体验已结束" description="体验账号已过期，请回到产品介绍页重新进入。" />
  ),
})
