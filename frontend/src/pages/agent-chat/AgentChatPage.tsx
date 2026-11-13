import { useEffect } from 'react'
import { Link, Outlet, useNavigate, useParams, useRouterState } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'
import { ring } from 'ldrs'

import { AgentAvatar } from '@/components/brand/AgentAvatar'
import { Badge } from '@/components/ui/badge'
import { useCurrentConversationId } from '@/hooks/useConversationActions'
import { useAgentConversationTitle, useAgentSession } from '@/stores/agent-session'
import { disposeAllChatStores } from '@/stores/chat-registry'
import { useSidebarMode } from '@/stores/sidebar-mode'
import { useTabTitle } from '@/stores/use-tab-sync'

ring.register()

/**
 * 单 Agent 对话页外壳 —— /chat/:agentId，子路由是 /new 与 /c/:conversationId。
 *
 * 数据读 agent-session store（侧栏共用）。负责三件事：进页面把侧栏切到 Agent 模式并
 * 选中这个 Agent；网址没指向有效会话时跳到最近一条或新对话页；离开时回收对话桶。
 */
export default function AgentChatPage() {
  const { agentId } = useParams({ from: '/_authenticated/chat/$agentId' })
  const navigate = useNavigate()
  const agents = useAgentSession((s) => s.agents)
  const agentsLoaded = useAgentSession((s) => s.agentsLoaded)
  const loadAgents = useAgentSession((s) => s.loadAgents)
  const setActiveAgent = useAgentSession((s) => s.setActiveAgent)
  const conversations = useAgentSession((s) => s.conversations)
  const convLoadedFor = useAgentSession((s) => s.convLoadedFor)
  const setMode = useSidebarMode((s) => s.setMode)
  const titleOf = useAgentConversationTitle()
  const currentConvId = useCurrentConversationId()
  const onNewPage = useRouterState({
    select: (s) => s.matches.some((m) => m.routeId === '/_authenticated/chat/$agentId/new'),
  })

  const agent = agents.find((a) => a.id === agentId)

  useEffect(() => {
    if (!agentsLoaded) loadAgents()
  }, [agentsLoaded, loadAgents])

  useEffect(() => {
    setMode('agent')
  }, [setMode])

  useEffect(() => {
    if (agent) setActiveAgent(agent.id)
  }, [agent, setActiveAgent])

  // 离开 / 换 Agent → 回收所有对话桶（含在跑的流），与工作空间页同一口径
  useEffect(() => () => disposeAllChatStores(), [agentId])

  useTabTitle(`/chat/${agentId}`, agent?.name)

  // 网址既不是新对话页、也不指向列表里的会话 → 跳最近一条；一条都没有就去新对话页
  useEffect(() => {
    if (convLoadedFor !== agentId || onNewPage) return
    if (currentConvId && conversations.some((c) => c.id === currentConvId)) return
    if (conversations.length > 0) {
      navigate({
        to: '/chat/$agentId/c/$conversationId',
        params: { agentId, conversationId: conversations[0].id },
        replace: true,
      })
    } else {
      navigate({ to: '/chat/$agentId/new', params: { agentId }, replace: true })
    }
  }, [convLoadedFor, agentId, onNewPage, currentConvId, conversations, navigate])

  if (!agentsLoaded) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-center">
        <p className="text-foreground text-sm font-medium">Agent 不存在</p>
        <p className="text-muted-foreground text-xs">可能已被删除，或已下线</p>
        <Link
          to="/"
          className="text-brand mt-2 inline-flex items-center gap-1 text-sm hover:underline"
        >
          <ChevronLeft className="size-3.5" />
          返回首页
        </Link>
      </div>
    )
  }

  const current = conversations.find((c) => c.id === currentConvId)

  return (
    <div className="bg-background relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border shadow-sm">
      <div className="flex shrink-0 items-center gap-2 border-b px-4 py-2.5">
        <AgentAvatar
          seed={agent.id}
          src={agent.avatar_url}
          alt={agent.name}
          className="size-6 rounded-md"
        />
        <span className="truncate text-sm font-medium">{agent.name}</span>
        {!agent.usable && (
          <Badge variant="secondary" className="shrink-0">
            已下线
          </Badge>
        )}
        <span className="text-muted-foreground truncate text-sm">
          · {current ? titleOf(current) : '新对话'}
        </span>
      </div>
      <Outlet />
    </div>
  )
}
