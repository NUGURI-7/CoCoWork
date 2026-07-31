import { useCallback, useEffect, useState } from 'react'
import { ring } from 'ldrs'
import { BookOpen, Plug, Plus, Wrench } from 'lucide-react'

import { listMCPServers } from '@/api/mcp'
import { listSkills } from '@/api/skill'
import { listTools } from '@/api/tool'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { MCPServer, Skill, Tool } from '@/types'

import { CreateMcpServerDialog } from './CreateMcpServerDialog'
import { McpServerCard } from './McpServerCard'
import { SkillCard } from './SkillCard'
import { ToolCard } from './ToolCard'

ring.register()

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex-1 px-5 py-3">
      <div className="font-mono text-2xl leading-none font-medium tabular-nums">{value}</div>
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

function SkillGrid({ skills }: { skills: Skill[] }) {
  if (skills.length === 0) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-sm">
        <BookOpen className="size-8 opacity-40" />
        <p>暂无 skill</p>
      </div>
    )
  }
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))' }}
    >
      {skills.map((s) => (
        <SkillCard key={s.name} skill={s} />
      ))}
    </div>
  )
}

/** /tools — 工具与来源管理：内置工具 / Skill（均只读）+ MCP server（可增删改） */
export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[] | null>(null)
  const [skills, setSkills] = useState<Skill[] | null>(null)
  const [servers, setServers] = useState<MCPServer[] | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<MCPServer | null>(null)

  useEffect(() => {
    let cancelled = false
    listTools()
      .then((d) => {
        if (!cancelled) setTools(d)
      })
      .catch(() => {
        if (!cancelled) setTools([])
      })
    listSkills()
      .then((d) => {
        if (!cancelled) setSkills(d)
      })
      .catch(() => {
        if (!cancelled) setSkills([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loadServers = useCallback(() => {
    listMCPServers()
      .then(setServers)
      .catch(() => setServers([]))
  }, [])

  useEffect(() => {
    loadServers()
  }, [loadServers])

  if (tools === null || skills === null || servers === null) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  const builtin = tools.filter((t) => t.source_type === 'builtin')

  function openCreate() {
    setEditing(null)
    setDialogOpen(true)
  }

  function openEdit(server: MCPServer) {
    setEditing(server)
    setDialogOpen(true)
  }

  return (
    <div className="space-y-6">
      {/* ① Header 带 */}
      <div>
        <h1 className="text-xl font-semibold">工具</h1>
      </div>

      {/* ② 概览统计带 */}
      <div className="flex divide-x rounded-lg border">
        <Stat label="内置工具" value={builtin.length} />
        <Stat label="Skill" value={skills.length} />
        <Stat label="MCP server" value={servers.length} />
      </div>

      {/* ③ Tab：内置工具 / Skill（均只读）/ MCP（server 管理） */}
      <Tabs defaultValue="builtin">
        <TabsList>
          <TabsTrigger value="builtin">内置工具</TabsTrigger>
          <TabsTrigger value="skill">Skill</TabsTrigger>
          <TabsTrigger value="mcp">MCP</TabsTrigger>
        </TabsList>

        <TabsContent value="builtin" className="mt-4">
          <ToolGrid tools={builtin} />
        </TabsContent>

        <TabsContent value="skill" className="mt-4">
          <SkillGrid skills={skills} />
        </TabsContent>

        <TabsContent value="mcp" className="mt-4">
          <div className="space-y-4">
            <div className="flex justify-end">
              <Button onClick={openCreate}>
                <Plus />
                添加 MCP server
              </Button>
            </div>

            {servers.length === 0 ? (
              <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-sm">
                <Plug className="size-8 opacity-40" />
                <p>还没有 MCP server</p>
                <Button variant="outline" size="sm" onClick={openCreate}>
                  <Plus className="size-4" />
                  添加第一个
                </Button>
              </div>
            ) : (
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
                }}
              >
                {servers.map((s) => (
                  <McpServerCard
                    key={s.id}
                    server={s}
                    onEdit={openEdit}
                    onChanged={loadServers}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <CreateMcpServerDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editing={editing}
        onSaved={loadServers}
      />
    </div>
  )
}
