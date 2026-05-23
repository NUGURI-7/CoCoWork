import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { AgentCard } from './AgentCard'
import { mockAgents } from './mock'

/** /agents — Agent 列表页 */
export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Agents</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            管理和配置 AI Agent，发布后可进行对话
          </p>
        </div>
        <Button size="sm">
          <Plus className="size-4" />
          创建 Agent
        </Button>
      </div>

      <div className="space-y-3">
        {mockAgents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  )
}
