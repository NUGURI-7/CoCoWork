import type { ReactNode } from 'react'
import { PanelLeft } from 'lucide-react'

import {
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'

interface SidebarBrandProps {
  icon: ReactNode
  title: string
  onHome: () => void
}

/**
 * 侧栏顶部的品牌行 + 收起按钮。
 *
 * 展开时：品牌（点击回首页）+ 右侧收起按钮。
 * 收起时：只剩图标，悬停变成展开图标，点击展开侧栏。
 */
export function SidebarBrand({ icon, title, onHome }: SidebarBrandProps) {
  const { state, isMobile, toggleSidebar } = useSidebar()
  const collapsed = state === 'collapsed' && !isMobile

  return (
    <SidebarMenuItem className="flex items-center gap-1">
      <SidebarMenuButton
        tooltip={collapsed ? '展开侧边栏' : title}
        className="group/brand h-10 min-w-0 flex-1 gap-3 group-data-[collapsible=icon]:p-1!"
        onClick={collapsed ? toggleSidebar : onHome}
      >
        <span
          className={cn(
            'flex size-7 shrink-0 items-center justify-center group-data-[collapsible=icon]:size-6',
            collapsed && 'group-hover/brand:hidden',
          )}
        >
          {icon}
        </span>
        {collapsed && (
          <span className="hidden size-6 shrink-0 items-center justify-center group-hover/brand:flex">
            <PanelLeft className="size-4!" />
          </span>
        )}
        <span className="font-display truncate text-xl leading-none font-semibold tracking-tight">
          {title}
        </span>
      </SidebarMenuButton>
      {!collapsed && !isMobile && (
        <SidebarTrigger className="text-muted-foreground hover:text-foreground shrink-0" />
      )}
    </SidebarMenuItem>
  )
}
