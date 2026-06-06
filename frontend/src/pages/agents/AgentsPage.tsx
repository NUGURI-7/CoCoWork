import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Bot, Plus } from 'lucide-react'
import { ring } from 'ldrs'

import { listAgents } from '@/api/agent'
import { listAllModels } from '@/api/model'
import { Button } from '@/components/ui/button'
import { useHorizontalWheelScroll } from '@/hooks/use-horizontal-wheel-scroll'
import type { Agent, Template } from '@/types'
import { AgentCard } from './AgentCard'
import { CreateAgentDialog } from './CreateAgentDialog'
import { TemplateCard } from './TemplateCard'
import { mockTemplates } from './mock'

ring.register()

/** /agents — Agent 列表页（三带式：Header / 模板池 / 我的 Agent 网格） */
export default function AgentsPage() {
  const navigate = useNavigate()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [defaultTemplate, setDefaultTemplate] = useState<Template | null>(null)
  /** model id → display_name 反查表，让卡片显示真实模型名（不用 N+1 各自拉） */
  const [modelNameMap, setModelNameMap] = useState<Map<string, string>>(
    () => new Map(),
  )
  const templateScrollRef = useHorizontalWheelScroll<HTMLDivElement>()

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listAgents()
      setAgents(data)
    } catch {
      // 全局拦截器已 toast；保持空列表
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  // 一次性拉 chat 模型反查表（mount 时拉，创建/删除 agent 不重拉）
  useEffect(() => {
    listAllModels({ modelType: 'chat', enabledOnly: true })
      .then((ms) => setModelNameMap(new Map(ms.map((m) => [m.id, m.display_name]))))
      .catch(() => {})
  }, [])

  function handleCreateClick() {
    setDefaultTemplate(null)
    setDialogOpen(true)
  }

  function handleTemplateClick(template: Template) {
    setDefaultTemplate(template)
    setDialogOpen(true)
  }

  function handleCreated(agent: Agent) {
    setAgents((prev) => [agent, ...prev])
    navigate({ to: '/agents/$agentId', params: { agentId: agent.id } })
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
        onCreate={handleCreated}
      />

      {/* ③ 我的 Agent 网格 */}
      <section className="space-y-3">
        <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          我的 Agent
        </h2>
        {loading ? (
          <div className="flex min-h-[40vh] items-center justify-center">
            <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
          </div>
        ) : agents.length === 0 ? (
          <EmptyState onCreate={handleCreateClick} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                modelNameMap={modelNameMap}
                onDeleted={refetch}
              />
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
