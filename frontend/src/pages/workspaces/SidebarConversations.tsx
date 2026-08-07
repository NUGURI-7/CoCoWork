import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Check, ChevronsUpDown, Layers, MessageSquarePlus } from 'lucide-react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { softPalette } from '@/lib/avatar-color'
import { cn } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  SidebarGroup,
  SidebarMenuButton,
  SidebarSeparator,
  useSidebar,
} from '@/components/ui/sidebar'
import { useConversationActions } from '@/hooks/useConversationActions'
import { useWorkspaceSession } from '@/stores/workspace-session'
import {
  ConversationList,
  DeleteConversationDialog,
} from './ConversationList'

/**
 * 全局侧边栏的会话区 —— 空间选择器 + 新对话 + 当前空间会话列表（ChatGPT 式常驻）。
 *
 * 挂在 AppSidebar 导航与 footer 之间。数据全读 workspace-session store；选会话 /
 * 新建 / 删除的导航走 useConversationActions。空间为空时整块不渲染；侧栏收成 icon
 * 轨时整块隐藏（图标轨放不下列表）。
 */
export function SidebarConversations() {
  const navigate = useNavigate()
  const { isMobile } = useSidebar()
  const workspaces = useWorkspaceSession((s) => s.workspaces)
  const workspacesLoaded = useWorkspaceSession((s) => s.workspacesLoaded)
  const activeWorkspaceId = useWorkspaceSession((s) => s.activeWorkspaceId)
  const conversations = useWorkspaceSession((s) => s.conversations)
  const loadWorkspaces = useWorkspaceSession((s) => s.loadWorkspaces)
  const setActiveWorkspace = useWorkspaceSession((s) => s.setActiveWorkspace)

  const { currentConvId, select, createAndOpen, remove, rename } =
    useConversationActions()

  // 待确认删除的会话 id（null = 关闭弹窗）。放 DropdownMenu/列表之外，避免被连带卸载。
  const [confirmId, setConfirmId] = useState<string | null>(null)

  // 侧栏常驻 → 首次挂载拉一次空间列表（store 内部会校正 active + 拉会话）
  useEffect(() => {
    if (!workspacesLoaded) loadWorkspaces()
  }, [workspacesLoaded, loadWorkspaces])

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId)

  // 还没有任何空间：整块不渲染（含分隔线）
  if (!activeWorkspace) return null

  function handleSwitchWorkspace(id: string) {
    setActiveWorkspace(id)
    navigate({ to: '/workspaces/$workspaceId', params: { workspaceId: id } })
  }

  return (
    <>
      <SidebarSeparator className="mx-0 group-data-[collapsible=icon]:hidden" />
      <SidebarGroup className="flex min-h-0 flex-1 flex-col gap-1.5 group-data-[collapsible=icon]:hidden">
        {/* 空间选择器 */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              className="h-10 data-[state=open]:bg-sidebar-accent"
              tooltip={activeWorkspace.name}
            >
              <WorkspaceAvatar workspace={activeWorkspace} />
              <span className="truncate font-medium">{activeWorkspace.name}</span>
              <ChevronsUpDown className="ml-auto size-4 opacity-50" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={isMobile ? 'bottom' : 'right'}
            align="start"
            sideOffset={4}
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
          >
            <DropdownMenuLabel className="text-muted-foreground text-xs">
              工作空间
            </DropdownMenuLabel>
            {workspaces.map((ws) => (
              <DropdownMenuItem
                key={ws.id}
                onClick={() => handleSwitchWorkspace(ws.id)}
                className="gap-2"
              >
                <WorkspaceAvatar workspace={ws} />
                <span className="truncate">{ws.name}</span>
                {ws.id === activeWorkspaceId && (
                  <Check className="text-brand ml-auto size-4 shrink-0" />
                )}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate({ to: '/workspaces' })}>
              <Layers className="size-4" />
              管理工作空间
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* 新对话 */}
        <SidebarMenuButton
          onClick={createAndOpen}
          className="text-muted-foreground hover:text-foreground"
        >
          <MessageSquarePlus className="size-4" />
          <span>新对话</span>
        </SidebarMenuButton>

        {/* 会话列表（独立滚动） */}
        <div className="-mx-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-1">
          <ConversationList
            conversations={conversations}
            currentId={currentConvId}
            onSelect={select}
            onRequestDelete={setConfirmId}
            onRename={(id, title) => void rename(id, title)}
          />
        </div>
      </SidebarGroup>

      <DeleteConversationDialog
        conversation={conversations.find((c) => c.id === confirmId)}
        open={confirmId !== null}
        onOpenChange={(o) => !o && setConfirmId(null)}
        onConfirm={() => {
          if (confirmId) remove(confirmId)
          setConfirmId(null)
        }}
      />
    </>
  )
}

function WorkspaceAvatar({
  workspace,
}: {
  workspace: { id: string; name: string; avatar_url: string }
}) {
  return (
    <Avatar className="size-6 rounded-md">
      <AvatarImage src={workspace.avatar_url || undefined} alt={workspace.name} />
      <AvatarFallback
        className={cn(
          'rounded-md text-[11px] font-medium',
          softPalette(workspace.id),
        )}
      >
        {workspace.name.slice(0, 1).toUpperCase()}
      </AvatarFallback>
    </Avatar>
  )
}
