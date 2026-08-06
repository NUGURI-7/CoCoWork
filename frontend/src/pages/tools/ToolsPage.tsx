import { useCallback, useEffect, useRef, useState } from 'react'
import { AxiosError } from 'axios'
import { ring } from 'ldrs'
import { BookOpen, Plug, Plus, Upload, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { listMCPServers } from '@/api/mcp'
import { listSkills, uploadSkill } from '@/api/skill'
import { listTools } from '@/api/tool'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiBusinessError } from '@/request'
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

function SkillGrid({
  skills,
  onChanged,
}: {
  skills: Skill[]
  onChanged: () => void
}) {
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
        <SkillCard key={s.id ?? s.name} skill={s} onDeleted={onChanged} />
      ))}
    </div>
  )
}

/** 后端的业务错误（409 撞名、400 包不合规）都带人话消息，尽量透出来 */
function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiBusinessError) return err.message
  if (err instanceof AxiosError) {
    const msg = err.response?.data?.message
    if (typeof msg === 'string') return msg
  }
  return fallback
}

/** /tools — 工具与来源管理：内置工具（只读）/ Skill（可传可删）/ MCP server（可增删改） */
export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[] | null>(null)
  const [skills, setSkills] = useState<Skill[] | null>(null)
  const [servers, setServers] = useState<MCPServer[] | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<MCPServer | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    listTools()
      .then((d) => {
        if (!cancelled) setTools(d)
      })
      .catch(() => {
        if (!cancelled) setTools([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loadSkills = useCallback(() => {
    listSkills()
      .then(setSkills)
      .catch(() => setSkills([]))
  }, [])

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

  async function handleFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // 清空才能连续选同一个文件（否则第二次不触发 change）
    if (!file) return

    setUploading(true)
    try {
      const created = await uploadSkill(file)
      toast.success(`已上传 ${created.name}`)
      loadSkills()
    } catch (err) {
      toast.error(errorMessage(err, '上传失败'))
    } finally {
      setUploading(false)
    }
  }

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

      {/* ③ Tab：内置工具（只读）/ Skill（可传可删）/ MCP（server 管理） */}
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
          <div className="space-y-4">
            <div className="flex items-center justify-end gap-3">
              <span className="text-muted-foreground text-xs">
                zip 包，内含 SKILL.md
              </span>
              <Button
                disabled={uploading}
                onClick={() => fileRef.current?.click()}
              >
                <Upload />
                {uploading ? '上传中...' : '上传 skill'}
              </Button>
            </div>
            <SkillGrid skills={skills} onChanged={loadSkills} />
          </div>
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

      {/* 真正的文件选择器藏起来，由上面那个按钮代触发 —— 原生 input 样式不可控 */}
      <input
        ref={fileRef}
        type="file"
        accept=".zip,application/zip"
        className="hidden"
        onChange={(e) => void handleFilePicked(e)}
      />

      <CreateMcpServerDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editing={editing}
        onSaved={loadServers}
      />
    </div>
  )
}
