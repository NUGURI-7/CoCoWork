import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import type { Agent, Template } from '@/types'
import { mockTemplates } from './mock'
import { iconMap } from './TemplateCard'

interface CreateAgentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 模板池卡片点击时预选 */
  defaultTemplate?: Template | null
  /** 创建后回调，父级负责 push 列表 + 跳详情 */
  onCreate: (agent: Agent) => void
}

export function CreateAgentDialog({
  open,
  onOpenChange,
  defaultTemplate,
  onCreate,
}: CreateAgentDialogProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [name, setName] = useState('')
  /** 用户手改过 name 后，再切模板不再覆盖 */
  const [nameTouched, setNameTouched] = useState(false)

  // 打开时重置（含预选模板）
  useEffect(() => {
    if (!open) return
    setSelectedId(defaultTemplate?.id ?? null)
    setName(defaultTemplate ? `我的${defaultTemplate.name}` : '')
    setNameTouched(false)
  }, [open, defaultTemplate])

  // 没动过 name 时，切模板自动填默认名
  useEffect(() => {
    if (nameTouched || !selectedId) return
    const t = mockTemplates.find((x) => x.id === selectedId)
    if (t) setName(`我的${t.name}`)
  }, [selectedId, nameTouched])

  const canCreate = !!selectedId && name.trim().length > 0

  function handleCreate() {
    const template = mockTemplates.find((t) => t.id === selectedId)
    if (!template || !name.trim()) return
    const now = new Date().toISOString()
    const newAgent: Agent = {
      id: crypto.randomUUID(),
      name: name.trim(),
      template_id: template.id,
      template_name: template.name,
      behavior_type: template.behavior_type,
      avatar_color: template.default_avatar_color,
      description: '',
      model_id: null,
      model_display_name: null,
      system_prompt: null,
      config: {},
      knowledge_ids: [],
      tool_ids: [],
      mcp_ids: [],
      created_at: now,
      updated_at: now,
    }
    onCreate(newAgent)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>创建 Agent</DialogTitle>
          <DialogDescription>选一个模板，起个名字</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* ① 模板选择 */}
          <div className="space-y-2">
            <Label className="text-xs font-medium tracking-wide uppercase">
              选择模板
            </Label>
            <div className="grid grid-cols-4 gap-2">
              {mockTemplates.map((t) => {
                const Icon = iconMap[t.icon] ?? Sparkles
                const isSelected = selectedId === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSelectedId(t.id)}
                    className={cn(
                      'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition',
                      isSelected
                        ? 'border-brand bg-brand-subtle text-brand'
                        : 'hover:bg-muted text-foreground',
                    )}
                  >
                    <Icon className={cn('size-5', !isSelected && 'text-brand')} />
                    <span className="text-xs font-medium">{t.name}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* ② 名字 */}
          <div className="space-y-2">
            <Label htmlFor="agent-name" className="text-xs font-medium tracking-wide uppercase">
              起个名字
            </Label>
            <Input
              id="agent-name"
              value={name}
              placeholder="我的研究员"
              onChange={(e) => {
                setName(e.target.value)
                setNameTouched(true)
              }}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canCreate} onClick={handleCreate}>
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
