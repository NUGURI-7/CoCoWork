import { useNavigate, useRouterState } from '@tanstack/react-router'
import { ArrowRight, LayoutDashboard, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react'

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
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import { UserMenu } from './UserMenu'
import { mainNav, type NavItem } from './nav.config'

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const navigate = useNavigate()
  const openTab = useWorkspaceTabsStore((s) => s.open)
  const isAdmin = useAuthStore((s) => s.user?.is_admin)

  function isActive(to: NavItem['to']) {
    if (to === '/') return pathname === '/'
    return pathname === to || pathname.startsWith(`${to}/`)
  }

  function handleNav(to: string, title: string, icon?: LucideIcon) {
    openTab({ path: to, title, icon })
    navigate({ to })
  }

  return (
    <Sidebar variant="floating" collapsible="icon">
      {/* 顶部 logo */}
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="CoCoWork"
              className="h-10 gap-3"
              onClick={() => handleNav('/', '主页', LayoutDashboard)}
            >
              <Sparkles />
              <span className="font-serif text-xl leading-none">CoCoWork</span>
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
                    isActive={isActive(item.to)}
                    tooltip={item.title}
                    className="h-10 gap-3 text-base"
                    onClick={() => handleNav(item.to as string, item.title, item.icon)}
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
          {isAdmin && (
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="后台管理"
                onClick={() => navigate({ to: '/admin' })}
              >
                <ShieldCheck />
                <span>后台管理</span>
                <ArrowRight className="ml-auto size-3.5 opacity-40" />
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <UserMenu />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
