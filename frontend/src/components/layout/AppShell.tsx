import type { ReactNode } from 'react'

import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'
import { useImmersiveStore } from '@/stores/immersive'
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
  // 沉浸模式：藏掉顶栏 + TabBar，内容区去掉留白铺满。页面侧负责开关与卸载复位。
  const immersive = useImmersiveStore((s) => s.active)
  return (
    <SidebarProvider className="h-svh">
      <AppSidebar />
      <SidebarInset className="min-w-0">
        {!immersive && (
          <>
            <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
              <SidebarTrigger className="-ml-1" />
              <Separator
                orientation="vertical"
                className="mr-2 data-[orientation=vertical]:h-4"
              />
            </header>
            <TabBar useStore={useWorkspaceTabsStore} />
          </>
        )}
        <div
          className={cn(
            'flex min-h-0 min-w-0 flex-1 flex-col',
            // 沉浸态收紧顶部留白（兑现「去留白铺满」意图）：顶 8 / 两侧·底 16
            immersive ? 'px-4 pt-2 pb-4' : 'gap-4 p-4',
          )}
        >
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
