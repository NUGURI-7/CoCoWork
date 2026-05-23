import { useNavigate, useRouterState } from '@tanstack/react-router'
import { ArrowLeft, ShieldCheck } from 'lucide-react'

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
import { useAdminTabsStore } from '@/stores/tab-store'
import { UserMenu } from './UserMenu'
import { adminNav, type AdminNavItem } from './admin-nav.config'

export function AdminSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const navigate = useNavigate()
  const openTab = useAdminTabsStore((s) => s.open)

  function isActive(to: AdminNavItem['to']) {
    if (to === '/admin') return pathname === '/admin'
    return pathname === to || pathname.startsWith(`${to}/`)
  }

  function handleNav(item: AdminNavItem) {
    openTab({ path: item.to as string, title: item.title, icon: item.icon })
    navigate({ to: item.to })
  }

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="管理后台"
              className="h-10 gap-3"
              onClick={() => handleNav({ to: '/admin', title: '概览', icon: ShieldCheck })}
            >
              <ShieldCheck />
              <span className="font-serif text-xl leading-none">管理后台</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {adminNav.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton
                    isActive={isActive(item.to)}
                    tooltip={item.title}
                    className="h-10 gap-3 text-base"
                    onClick={() => handleNav(item)}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="返回工作台"
              onClick={() => navigate({ to: '/' })}
            >
              <ArrowLeft />
              <span>返回工作台</span>
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
