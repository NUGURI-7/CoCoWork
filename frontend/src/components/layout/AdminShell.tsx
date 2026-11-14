import type { ReactNode } from 'react'

import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { useAdminTabsStore } from '@/stores/tab-store'
import { useTabSync } from '@/stores/use-tab-sync'
import { AdminSidebar } from './AdminSidebar'
import { TabBar } from './TabBar'

export function AdminShell({ children }: { children: ReactNode }) {
  useTabSync(useAdminTabsStore)
  return (
    <SidebarProvider className="h-svh">
      <AdminSidebar />
      <SidebarInset>
        {/* 桌面端的收起按钮在侧栏里；手机端侧栏是抽屉，入口留在这里 */}
        <header className="flex h-12 shrink-0 items-center border-b px-4 md:hidden">
          <SidebarTrigger className="-ml-1" />
        </header>
        <TabBar useStore={useAdminTabsStore} />
        {/* overflow-y-auto 不可省：外层 h-svh 锁死高度，没有滚动容器时超出一屏的
            内容会画到 SidebarInset 的圆角卡片外面（表现为边框中途断掉） */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
