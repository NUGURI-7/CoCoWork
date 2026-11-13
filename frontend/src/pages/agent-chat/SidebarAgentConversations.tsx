import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Check, ChevronsUpDown, MessageSquarePlus } from 'lucide-react'

import { AgentAvatar } from '@/components/brand/AgentAvatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SidebarGroup, SidebarMenuButton, useSidebar } from '@/components/ui/sidebar'
import { useAgentConversationActions } from '@/hooks/useAgentConversationActions'
import { useAgentConversationTitle, useAgentSession } from '@/stores/agent-session'
import { ConversationList, DeleteConversationDialog } from '@/pages/workspaces/ConversationList'
import { SidebarModeToggle } from './SidebarModeToggle'

/**
 * 侧栏会话区的 Agent 模式 —— Agent 选择器 + 新对话 + 这个 Agent 下的会话列表。
 * 已下线的 Agent 只在聊过的人这里出现，标「已下线」，能翻看、不能开新对话。
 */
export function SidebarAgentConversations() {
  const navigate = useNavigate()
  const { isMobile } = useSidebar()
  const agents = useAgentSession((s) => s.agents)
  const agentsLoaded = useAgentSession((s) => s.agentsLoaded)
  const activeAgentId = useAgentSession((s) => s.activeAgentId)
  const conversations = useAgentSession((s) => s.conversations)
  const loadAgents = useAgentSession((s) => s.loadAgents)
  const setActiveAgent = useAgentSession((s) => s.setActiveAgent)
  const titleOf = useAgentConversationTitle()
  const { currentConvId, select, createAndOpen, remove, rename } = useAgentConversationActions()
  const [confirmId, setConfirmId] = useState<string | null>(null)

  useEffect(() => {
    if (!agentsLoaded) loadAgents()
  }, [agentsLoaded, loadAgents])

  const activeAgent = agents.find((a) => a.id === activeAgentId)

  function handleSwitchAgent(id: string) {
    setActiveAgent(id)
    navigate({ to: '/chat/$agentId', params: { agentId: id } })
  }

  return (
    <>
      <SidebarGroup className="flex min-h-0 flex-1 flex-col gap-1.5 group-data-[collapsible=icon]:hidden">
        <div className="flex items-center gap-1">
          {activeAgent ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  className="h-10 min-w-0 flex-1 data-[state=open]:bg-sidebar-accent"
                  tooltip={activeAgent.name}
                >
                  <AgentAvatar
                    seed={activeAgent.id}
                    src={activeAgent.avatar_url}
                    alt={activeAgent.name}
                    className="size-6 shrink-0 rounded-md"
                  />
                  <span className="truncate font-medium">{activeAgent.name}</span>
                  {!activeAgent.usable && (
                    <span className="text-muted-foreground shrink-0 text-[11px]">已下线</span>
                  )}
                  <ChevronsUpDown className="ml-auto size-4 shrink-0 opacity-50" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side={isMobile ? 'bottom' : 'right'}
                align="start"
                sideOffset={4}
                className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
              >
                <DropdownMenuLabel className="text-muted-foreground text-xs">
                  Agent
                </DropdownMenuLabel>
                {agents.map((a) => (
                  <DropdownMenuItem
                    key={a.id}
                    onClick={() => handleSwitchAgent(a.id)}
                    className="gap-2"
                  >
                    <AgentAvatar
                      seed={a.id}
                      src={a.avatar_url}
                      alt={a.name}
                      className="size-6 shrink-0 rounded-md"
                    />
                    <span className="truncate">{a.name}</span>
                    {!a.usable && (
                      <span className="text-muted-foreground shrink-0 text-[11px]">已下线</span>
                    )}
                    {a.id === activeAgentId && (
                      <Check className="text-brand ml-auto size-4 shrink-0" />
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <div className="text-muted-foreground flex h-10 flex-1 items-center px-2 text-sm">
              {agentsLoaded ? '还没有可用的 Agent' : '加载中…'}
            </div>
          )}
          <SidebarModeToggle />
        </div>

        {activeAgent && (
          <>
            <SidebarMenuButton
              onClick={createAndOpen}
              disabled={!activeAgent.usable}
              className="text-muted-foreground hover:text-foreground"
            >
              <MessageSquarePlus className="size-4" />
              <span>新对话</span>
            </SidebarMenuButton>

            <div className="-mx-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-1">
              <ConversationList
                conversations={conversations}
                currentId={currentConvId}
                onSelect={select}
                onRequestDelete={setConfirmId}
                onRename={(id, title) => void rename(id, title)}
                titleOf={titleOf}
              />
            </div>
          </>
        )}
      </SidebarGroup>

      <DeleteConversationDialog
        conversation={conversations.find((c) => c.id === confirmId)}
        open={confirmId !== null}
        onOpenChange={(o) => !o && setConfirmId(null)}
        onConfirm={() => {
          if (confirmId) remove(confirmId)
          setConfirmId(null)
        }}
        titleOf={titleOf}
      />
    </>
  )
}
