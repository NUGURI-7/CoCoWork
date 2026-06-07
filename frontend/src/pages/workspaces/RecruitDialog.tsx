import { useEffect, useState } from 'react'
import { v4 as uuidv4 } from 'uuid'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { mockTemplates } from '@/pages/agents/mock'
import type { BehaviorType, Template, WorkspaceMember } from '@/types'

/** mockAgents 已下线（agents 列表接真后端）；workspace 切片本身也未接真接口，
 *  「从我的 Agent」tab 暂以空数组占位，下一口跟 workspace 切片一起接 `listAgents()`。 */
type AgentLite = {
  id: string
  name: string
  avatar_color: string
  behavior_type: BehaviorType
  template_name: string
}
const mockAgents: AgentLite[] = []

/** mock 时代 `template.behavior_type` 已删，UI 仍需一个 BehaviorType 取值——按 kind 派生。 */
function templateBehavior(t: Template): BehaviorType {
  return t.kind === 'graph' ? 'supervisor' : 'single'
}

interface RecruitDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 招募成功回调，父级负责 push 进 workspace.members */
  onRecruit: (member: WorkspaceMember) => void
}

type SourceTab = 'template' | 'agent'

/**
 * 招募成员弹窗（spec §5.2）
 *
 * 两种来源：
 * - 模板（毛坯空壳，空间注入全套）
 * - 我的 Agent（已装好资源，叠加空间注入）
 *
 * 招进来都是该空间的实例，跟源脱钩（v0 简化为复制基础字段）。
 */
export function RecruitDialog({ open, onOpenChange, onRecruit }: RecruitDialogProps) {
  const [tab, setTab] = useState<SourceTab>('template')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setTab('template')
    setSelectedTemplateId(null)
    setSelectedAgentId(null)
  }, [open])

  const canRecruit = tab === 'template' ? !!selectedTemplateId : !!selectedAgentId

  function handleRecruit() {
    if (tab === 'template') {
      const t = mockTemplates.find((x) => x.id === selectedTemplateId)
      if (!t) return
      onRecruit({
        id: uuidv4(),
        name: t.name,
        avatar_color: t.default_avatar_color,
        role: 'agent',
        source: 'template',
        source_name: t.name,
        behavior_type: templateBehavior(t),
      })
    } else {
      const a = mockAgents.find((x) => x.id === selectedAgentId)
      if (!a) return
      onRecruit({
        id: uuidv4(),
        name: a.name,
        avatar_color: a.avatar_color,
        role: 'agent',
        source: 'agent',
        source_name: a.name,
        behavior_type: a.behavior_type,
      })
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>招募成员</DialogTitle>
          <DialogDescription>
            选模板招毛坯（空间注入全套），或招你已建好的 Agent（自带 prompt/资源 + 空间注入）
          </DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={(v) => setTab(v as SourceTab)}>
          <TabsList>
            <TabsTrigger value="template">从模板</TabsTrigger>
            <TabsTrigger value="agent">从我的 Agent</TabsTrigger>
          </TabsList>

          <TabsContent value="template" className="mt-3">
            <div className="grid max-h-72 grid-cols-2 gap-2 overflow-y-auto">
              {mockTemplates.map((t) => {
                const sel = selectedTemplateId === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSelectedTemplateId(t.id)}
                    className={cn(
                      'flex items-center gap-3 rounded-lg border p-3 text-left transition',
                      sel
                        ? 'border-brand bg-brand-subtle'
                        : 'hover:bg-muted',
                    )}
                  >
                    <div
                      className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
                      style={{ backgroundColor: t.default_avatar_color }}
                    >
                      {t.name.slice(0, 1)}
                    </div>
                    <div className="min-w-0">
                      <div className={cn('truncate text-sm font-medium', sel && 'text-brand')}>
                        {t.name}
                      </div>
                      <div className="text-muted-foreground truncate text-xs">
                        {t.description}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </TabsContent>

          <TabsContent value="agent" className="mt-3">
            {mockAgents.length === 0 ? (
              <p className="text-muted-foreground py-8 text-center text-sm">
                你还没创建 Agent
              </p>
            ) : (
              <div className="grid max-h-72 grid-cols-2 gap-2 overflow-y-auto">
                {mockAgents.map((a) => {
                  const sel = selectedAgentId === a.id
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => setSelectedAgentId(a.id)}
                      className={cn(
                        'flex items-center gap-3 rounded-lg border p-3 text-left transition',
                        sel
                          ? 'border-brand bg-brand-subtle'
                          : 'hover:bg-muted',
                      )}
                    >
                      <div
                        className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
                        style={{ backgroundColor: a.avatar_color }}
                      >
                        {a.name.slice(0, 1)}
                      </div>
                      <div className="min-w-0">
                        <div className={cn('truncate text-sm font-medium', sel && 'text-brand')}>
                          {a.name}
                        </div>
                        <div className="text-muted-foreground truncate text-xs">
                          基于「{a.template_name}」
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canRecruit} onClick={handleRecruit}>
            招募
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
