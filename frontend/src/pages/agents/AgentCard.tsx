import { useNavigate } from '@tanstack/react-router'
import {
  Bot,
  BookOpen,
  CircleDot,
  MessageSquare,
  Network,
  Wrench,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { Agent } from '@/types'

/** Agent 类型 → 标签 */
const agentTypeLabel: Record<string, string> = {
  agent: 'Agent',
  flow: 'Flow',
  persona: 'Persona',
}

/** Agent 类型 → 图标 */
const agentTypeIcon: Record<string, typeof Bot> = {
  agent: Bot,
  flow: Network,
  persona: CircleDot,
}

/** 相对时间（简易版） */
function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

export function AgentCard({ agent }: { agent: Agent }) {
  const navigate = useNavigate()
  const openTab = useWorkspaceTabsStore((s) => s.open)

  function handleClick() {
    openTab({
      path: `/agents/${agent.id}`,
      title: agent.name,
      icon: Bot,
    })
    navigate({ to: '/agents/$agentId', params: { agentId: agent.id } })
  }

  const TypeIcon = agentTypeIcon[agent.agent_type] ?? CircleDot

  return (
    <Card
      className="card-interactive px-5 py-8"
      onClick={handleClick}
    >
      <div className="flex items-start justify-between gap-4">
        {/* 左侧：主体信息 */}
        <div className="min-w-0 flex-1 space-y-2.5">
          {/* 第一行：名称 + 状态 */}
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-medium">{agent.name}</h3>
            {agent.status === 'published' ? (
              <Badge variant="default" className="shrink-0 text-[10px]">
                已发布
              </Badge>
            ) : (
              <Badge variant="secondary" className="shrink-0 text-[10px]">
                草稿
              </Badge>
            )}
          </div>

          {/* 第二行：描述 */}
          <p className="text-muted-foreground line-clamp-1 text-xs">
            {agent.description || '暂无描述'}
          </p>

          {/* 第三行：元数据 */}
          <div className="text-muted-foreground flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1">
              <TypeIcon className="size-3" />
              {agentTypeLabel[agent.agent_type] ?? agent.agent_type}
            </span>
            {agent.model_display_name && (
              <span className="inline-flex items-center gap-1">
                <Bot className="size-3" />
                {agent.model_display_name}
              </span>
            )}
            {agent.tool_count > 0 && (
              <span className="inline-flex items-center gap-1">
                <Wrench className="size-3" />
                {agent.tool_count} 个工具
              </span>
            )}
            {agent.knowledge_count > 0 && (
              <span className="inline-flex items-center gap-1">
                <BookOpen className="size-3" />
                {agent.knowledge_count} 个知识库
              </span>
            )}
            <span className="ml-auto">{timeAgo(agent.updated_at)}</span>
          </div>
        </div>

        {/* 右侧：对话按钮 */}
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          disabled={agent.status !== 'published'}
          onClick={(e) => {
            e.stopPropagation()
            // TODO: 跳转到对话页面
            console.log('Open chat for agent:', agent.id)
          }}
        >
          <MessageSquare className="size-3.5" />
          对话
        </Button>
      </div>
    </Card>
  )
}
