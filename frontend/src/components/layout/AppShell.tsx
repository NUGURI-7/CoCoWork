import type { ReactNode } from 'react'

import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import { useTabSync } from '@/stores/use-tab-sync'
import { AppSidebar } from './AppSidebar'
import { TabBar } from './TabBar'

/**
 * 工作台外壳：左侧 sidebar + 顶栏 + 标签栏 + 内容区。
 * 由 _authenticated 布局路由渲染，子页面通过 children（<Outlet />）注入内容区。
 */
export function AppShell({ children }: { children: ReactNode }) {
  useTabSync(useWorkspaceTabsStore)
  return (
    <SidebarProvider className="h-svh">
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
        </header>
        <TabBar useStore={useWorkspaceTabsStore} />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 p-4">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  )
}
