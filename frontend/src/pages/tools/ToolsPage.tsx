import { useEffect, useState } from 'react'
import { ring } from 'ldrs'
import { Wrench } from 'lucide-react'

import { listTools } from '@/api/tool'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Tool, ToolSource } from '@/types'
import { ToolCard } from './ToolCard'

ring.register()

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex-1 px-5 py-3">
      <div className="font-serif text-2xl leading-none">{value}</div>
      <div className="text-muted-foreground mt-1 text-xs">{label}</div>
    </div>
  )
}

function ToolGrid({ tools }: { tools: Tool[] }) {
  if (tools.length === 0) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-sm">
        <Wrench className="size-8 opacity-40" />
        <p>暂无工具</p>
      </div>
    )
  }
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))' }}
    >
      {tools.map((t) => (
        <ToolCard key={t.name} tool={t} />
      ))}
    </div>
  )
}

/** /tools — 工具目录（只读：三带式 Header / 统计带 / Tab + 卡片网格） */
export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[] | null>(null)

  useEffect(() => {
    let cancelled = false
    listTools()
      .then((data) => {
        if (!cancelled) setTools(data)
      })
      .catch(() => {
        // 拦截器已 toast；失败按空列表收场
        if (!cancelled) setTools([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (tools === null) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  const builtin = tools.filter((t) => t.source_type === 'builtin')
  const mcp = tools.filter((t) => t.source_type === 'mcp')

  const byTab: Record<'all' | ToolSource, Tool[]> = {
    all: tools,
    builtin,
    mcp,
    custom: tools.filter((t) => t.source_type === 'custom'),
  }

  return (
    <div className="space-y-6">
      {/* ① Header 带 */}
      <div>
        <h1 className="text-xl font-semibold">工具</h1>
      </div>

      {/* ② 概览统计带 */}
      <div className="flex divide-x rounded-lg border">
        <Stat label="工具" value={tools.length} />
        <Stat label="内置" value={builtin.length} />
        <Stat label="MCP" value={mcp.length} />
      </div>

      {/* ③ Tab 按来源筛 + 卡片网格 */}
      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">全部</TabsTrigger>
          <TabsTrigger value="builtin">内置</TabsTrigger>
          <TabsTrigger value="mcp">MCP</TabsTrigger>
        </TabsList>

        {(['all', 'builtin', 'mcp'] as const).map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4">
            <ToolGrid tools={byTab[tab]} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
