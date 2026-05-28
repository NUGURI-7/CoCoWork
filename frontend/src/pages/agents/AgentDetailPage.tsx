import { Link, useParams } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { useTabTitle } from '@/stores/use-tab-sync'
import { ConfigPanel } from './ConfigPanel'
import { Playground } from './Playground'
import { useAgentMockStore } from './agent-mock-store'

/**
 * /agents/$agentId — Agent 详情页
 *
 * 创作者视角：左栏配置 + 右栏沙盒试运行。正式对话不在这里——归 workspace 模块统一管。
 * 左 40% / 右 60%。沙盒消息不持久化，刷新即清。
 */
export default function AgentDetailPage() {
  const { agentId } = useParams({ from: '/_authenticated/agents/$agentId' })
  const agent = useAgentMockStore((s) => s.getById(agentId))

  useTabTitle(agent?.name)

  if (!agent) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-center">
        <p className="text-foreground text-sm font-medium">Agent 不存在</p>
        <p className="text-muted-foreground text-xs">
          可能已被删除，或刷新后丢失（v0 mock 是内存存储）
        </p>
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
          <ConfigPanel agent={agent} />
        </div>

        <div className="flex w-3/5 min-h-0 flex-col">
          <Playground agent={agent} />
        </div>
      </div>
    </div>
  )
}
