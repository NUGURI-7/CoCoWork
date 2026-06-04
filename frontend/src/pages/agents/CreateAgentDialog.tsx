import { useEffect, useState } from 'react'
import { AxiosError } from 'axios'
import { Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { createAgent, type AgentCreatePayload } from '@/api/agent'
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
import { KindBadge } from './KindBadge'
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
  const [submitting, setSubmitting] = useState(false)

  // 打开时重置（含预选模板）
  useEffect(() => {
    if (!open) return
    setSelectedId(defaultTemplate?.id ?? null)
    setName(defaultTemplate ? `我的${defaultTemplate.name}` : '')
    setNameTouched(false)
    setSubmitting(false)
  }, [open, defaultTemplate])

  // 没动过 name 时，切模板自动填默认名
  useEffect(() => {
    if (nameTouched || !selectedId) return
    const t = mockTemplates.find((x) => x.id === selectedId)
    if (t) setName(`我的${t.name}`)
  }, [selectedId, nameTouched])

  const selectedTemplate = mockTemplates.find((t) => t.id === selectedId) ?? null
  const canCreate =
    !!selectedTemplate &&
    !selectedTemplate.disabled &&
    name.trim().length > 0 &&
    !submitting

  async function handleCreate() {
    if (!selectedTemplate || selectedTemplate.disabled || !name.trim()) return
    setSubmitting(true)
    const payload: AgentCreatePayload = {
      name: name.trim(),
      description: '',
      template: selectedTemplate.key,
      config: {
        avatar_color: selectedTemplate.default_avatar_color,
      },
    }
    try {
      const created = await createAgent(payload)
      toast.success(`Agent「${created.name}」已创建`)
      onCreate(created)
      onOpenChange(false)
    } catch (err) {
      const msg =
        err instanceof AxiosError ? err.response?.data?.message : null
      toast.error(typeof msg === 'string' ? msg : '创建失败')
    } finally {
      setSubmitting(false)
    }
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
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {mockTemplates.map((t) => {
                const Icon = iconMap[t.icon] ?? Sparkles
                const isSelected = selectedId === t.id
                const isDisabled = t.disabled === true
                return (
                  <button
                    key={t.id}
                    type="button"
                    disabled={isDisabled}
                    onClick={() => setSelectedId(t.id)}
                    className={cn(
                      'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition',
                      isDisabled
                        ? 'cursor-not-allowed opacity-50'
                        : isSelected
                          ? 'border-brand bg-brand-subtle text-brand'
                          : 'hover:bg-muted text-foreground',
                    )}
                  >
                    <Icon
                      className={cn(
                        'size-5',
                        !isSelected && !isDisabled && 'text-brand',
                      )}
                    />
                    <span className="text-xs font-medium">{t.name}</span>
                    <KindBadge kind={t.kind} />
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
              placeholder="我的通用 Agent"
              onChange={(e) => {
                setName(e.target.value)
                setNameTouched(true)
              }}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" disabled={submitting} onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canCreate} onClick={handleCreate}>
            {submitting ? '创建中…' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
