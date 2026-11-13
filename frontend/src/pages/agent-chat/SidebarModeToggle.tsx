import { useNavigate } from '@tanstack/react-router'
import { ArrowLeftRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useAgentSession } from '@/stores/agent-session'
import { useSidebarMode } from '@/stores/sidebar-mode'
import { useWorkspaceSession } from '@/stores/workspace-session'

/**
 * 侧栏会话区的模式切换：工作空间 ⇄ 单个 Agent。
 * 切过去顺带打开上次用的那个空间 / Agent，没有就去对应的列表页。
 */
export function SidebarModeToggle() {
  const navigate = useNavigate()
  const mode = useSidebarMode((s) => s.mode)
  const setMode = useSidebarMode((s) => s.setMode)
  const activeWorkspaceId = useWorkspaceSession((s) => s.activeWorkspaceId)
  const activeAgentId = useAgentSession((s) => s.activeAgentId)

  const toAgent = mode === 'workspace'

  function handleToggle() {
    if (toAgent) {
      setMode('agent')
      if (activeAgentId) navigate({ to: '/chat/$agentId', params: { agentId: activeAgentId } })
    } else {
      setMode('workspace')
      if (activeWorkspaceId) {
        navigate({ to: '/workspaces/$workspaceId', params: { workspaceId: activeWorkspaceId } })
      } else {
        navigate({ to: '/workspaces' })
      }
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={toAgent ? '切换到 Agent 对话' : '切换到工作空间'}
          onClick={handleToggle}
          className="text-muted-foreground hover:text-foreground size-8 shrink-0"
        >
          <ArrowLeftRight className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">
        {toAgent ? '切换到 Agent 对话' : '切换到工作空间'}
      </TooltipContent>
    </Tooltip>
  )
}
