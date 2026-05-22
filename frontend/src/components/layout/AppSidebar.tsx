import { Link, useRouterState } from '@tanstack/react-router'
import { Settings, Sparkles } from 'lucide-react'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { UserMenu } from './UserMenu'
import { mainNav, type NavItem } from './nav.config'

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  function isActive(to: NavItem['to']) {
    if (to === '/') return pathname === '/'
    return pathname === to || pathname.startsWith(`${to}/`)
  }

  return (
    <Sidebar variant="floating" collapsible="icon">
      {/* 顶部 logo —— 用与导航相同的 size-5 图标槽，保证图标列 + 文字列对齐 */}
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="CoCoWork" className="gap-3 [&>svg]:size-5">
              <Link to="/">
                <Sparkles />
                <span className="font-serif text-xl leading-none">CoCoWork</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNav.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton
                    asChild
                    size="lg"
                    isActive={isActive(item.to)}
                    tooltip={item.title}
                    className="gap-3 text-base [&>svg]:size-5"
                  >
                    <Link to={item.to}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* footer：设置（独立一行） + 头像卡片（点击弹下拉菜单） */}
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="设置">
              <Link to="/settings">
                <Settings />
                <span>设置</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <UserMenu />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
