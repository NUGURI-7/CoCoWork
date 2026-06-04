import { useEffect, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'
import { ring } from 'ldrs'

import { getAgent } from '@/api/agent'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Agent } from '@/types'
import { ConfigPanel } from './ConfigPanel'
import { Playground } from './Playground'

ring.register()

/**
 * /agents/$agentId — Agent 详情页
 *
 * 创作者视角：左栏配置 + 右栏沙盒试运行。正式对话不在这里——归 workspace 模块。
 * 左 40% / 右 60%。沙盒消息不持久化，刷新即清。
 */
export default function AgentDetailPage() {
  const { agentId } = useParams({ from: '/_authenticated/agents/$agentId' })
  const [agent, setAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setNotFound(false)
    getAgent(agentId)
      .then((data) => {
        if (!cancelled) setAgent(data)
      })
      .catch(() => {
        if (!cancelled) setNotFound(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [agentId])

  useTabTitle(`/agents/${agentId}`, agent?.name)

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  if (notFound || !agent) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-center">
        <p className="text-foreground text-sm font-medium">Agent 不存在</p>
        <p className="text-muted-foreground text-xs">可能已被删除或不属于你</p>
        <Link
          to="/agents"
          className="text-brand mt-2 inline-flex items-center gap-1 text-sm hover:underline"
        >
          <ChevronLeft className="size-3.5" />
          返回 Agents
        </Link>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      {/* 顶栏：面包屑 */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/agents" className="inline-flex items-center gap-1">
                <ChevronLeft className="size-3.5" />
                Agents
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{agent.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* 左配 40 / 右聊 60 */}
      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
        <div className="flex w-2/5 min-h-0 flex-col overflow-hidden">
          <ConfigPanel agent={agent} onSaved={setAgent} />
        </div>

        <div className="flex w-3/5 min-h-0 flex-col">
          <Playground agent={agent} />
        </div>
      </div>
    </div>
  )
}
