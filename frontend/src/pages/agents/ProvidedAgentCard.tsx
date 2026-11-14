import { useNavigate } from '@tanstack/react-router'
import { MessageSquare } from 'lucide-react'

import { AgentAvatar } from '@/components/brand/AgentAvatar'
import { Card, CardContent } from '@/components/ui/card'
import type { AgentBrief } from '@/types'

/**
 * 管理员提供给全员的 Agent —— 员工只能用，点卡片直接进对话，
 * 没有配置页、没有编辑和删除。
 */
export function ProvidedAgentCard({ agent }: { agent: AgentBrief }) {
  const navigate = useNavigate()

  return (
    <Card
      className="card-interactive w-56 shrink-0 gap-0 py-0"
      onClick={() => navigate({ to: '/chat/$agentId/new', params: { agentId: agent.id } })}
    >
      <CardContent className="flex h-full flex-col gap-2.5 p-4">
        <AgentAvatar seed={agent.id} src={agent.avatar_url} alt={agent.name} />
        <h4 className="leading-tight font-medium">{agent.name}</h4>
        <p className="text-muted-foreground line-clamp-2 flex-1 text-xs leading-relaxed">
          {agent.description || '可直接使用'}
        </p>
        <span className="text-brand mt-1 inline-flex items-center gap-1 self-start text-xs font-medium">
          <MessageSquare className="size-3.5" />
          开始使用
        </span>
      </CardContent>
    </Card>
  )
}
