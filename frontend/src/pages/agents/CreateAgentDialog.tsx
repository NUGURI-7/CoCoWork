import { useEffect, useState } from 'react'
import { AxiosError } from 'axios'
import { toast } from 'sonner'

import { createAgent, type AgentCreatePayload } from '@/api/agent'
import { useTemplates, findTemplate } from '@/hooks/use-templates'
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
import { templateIcon } from './TemplateCard'

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
  const { templates } = useTemplates()
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [name, setName] = useState('')
  /** 用户手改过 name 后，再切模板不再覆盖 */
  const [nameTouched, setNameTouched] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 打开时重置（含预选模板）
  useEffect(() => {
    if (!open) return
    setSelectedKey(defaultTemplate?.key ?? null)
    setName(defaultTemplate ? `我的 ${defaultTemplate.name}` : '')
    setNameTouched(false)
    setSubmitting(false)
  }, [open, defaultTemplate])

  // 没动过 name 时，切模板自动填默认名
  useEffect(() => {
    if (nameTouched || !selectedKey) return
    const t = findTemplate(templates, selectedKey)
    if (t) setName(`我的 ${t.name}`)
  }, [selectedKey, nameTouched, templates])

  const selectedTemplate = selectedKey ? findTemplate(templates, selectedKey) : null
  const canCreate = !!selectedTemplate && name.trim().length > 0 && !submitting

  async function handleCreate() {
    if (!selectedTemplate || !name.trim()) return
    setSubmitting(true)
    const payload: AgentCreatePayload = {
      name: name.trim(),
      description: '',
      template: selectedTemplate.key,
      config: {},
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
              {templates.map((t) => {
                const Icon = templateIcon(t.form)
                const isSelected = selectedKey === t.key
                return (
                  <button
                    key={t.key}
                    type="button"
                    title={t.description}
                    onClick={() => setSelectedKey(t.key)}
                    className={cn(
                      'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition',
                      isSelected
                        ? 'border-brand bg-brand-subtle text-brand'
                        : 'hover:bg-muted text-foreground',
                    )}
                  >
                    <Icon className={cn('size-5', !isSelected && 'text-brand')} />
                    <span className="text-xs font-medium">{t.name}</span>
                    <KindBadge kind={t.form} />
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
