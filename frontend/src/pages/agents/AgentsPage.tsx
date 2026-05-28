import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Bot, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useHorizontalWheelScroll } from '@/hooks/use-horizontal-wheel-scroll'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { Agent, Template } from '@/types'
import { AgentCard } from './AgentCard'
import { CreateAgentDialog } from './CreateAgentDialog'
import { TemplateCard } from './TemplateCard'
import { useAgentMockStore } from './agent-mock-store'
import { mockTemplates } from './mock'

/** /agents — Agent 列表页（三带式：Header / 模板池 / 我的 Agent 网格） */
export default function AgentsPage() {
  const navigate = useNavigate()
  const agents = useAgentMockStore((s) => s.agents)
  const addAgent = useAgentMockStore((s) => s.add)
  const removeAgent = useAgentMockStore((s) => s.remove)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [defaultTemplate, setDefaultTemplate] = useState<Template | null>(null)
  const templateScrollRef = useHorizontalWheelScroll<HTMLDivElement>()

  function handleCreateClick() {
    setDefaultTemplate(null)
    setDialogOpen(true)
  }

  function handleTemplateClick(template: Template) {
    setDefaultTemplate(template)
    setDialogOpen(true)
  }

  function handleCreate(agent: Agent) {
    addAgent(agent)
    toast.success(`Agent「${agent.name}」已创建`)
    navigate({ to: '/agents/$agentId', params: { agentId: agent.id } })
  }

  function handleDelete(id: string) {
    removeAgent(id)
    useWorkspaceTabsStore.getState().close(`/agents/${id}`)
  }

  return (
    <div className="min-w-0 space-y-8">
      {/* ① Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Agents</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Agent 是你基于模板装备的资产 —— 选模型、写 prompt、挂知识库和工具。
          </p>
        </div>
        <Button size="sm" onClick={handleCreateClick}>
          <Plus className="size-4" />
          创建 Agent
        </Button>
      </div>

      {/* ② 模板池横向卡片条 */}
      <section className="space-y-3">
        <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          从模板开始
        </h2>
        <div ref={templateScrollRef} className="-mx-2 -my-2 overflow-x-auto px-2 py-2">
          <div className="flex gap-3">
            {mockTemplates.map((t) => (
              <TemplateCard key={t.id} template={t} onClick={handleTemplateClick} />
            ))}
          </div>
        </div>
      </section>

      <CreateAgentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        defaultTemplate={defaultTemplate}
        onCreate={handleCreate}
      />

      {/* ③ 我的 Agent 网格 */}
      <section className="space-y-3">
        <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          我的 Agent
        </h2>
        {agents.length === 0 ? (
          <EmptyState onCreate={handleCreateClick} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {agents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} onDelete={handleDelete} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="text-muted-foreground flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-16 text-center">
      <Bot className="size-8" />
      <div className="space-y-1">
        <div className="text-foreground text-sm font-medium">你还没创建 Agent</div>
        <div className="text-xs">从上方模板开始装备一个</div>
      </div>
      <Button size="sm" variant="outline" onClick={onCreate}>
        <Plus className="size-4" />
        创建 Agent
      </Button>
    </div>
  )
}
