import { useEffect, useMemo, useState } from 'react'
import { Crown, X } from 'lucide-react'
import { toast } from 'sonner'

import { listAllModels } from '@/api/model'
import { updateWorkspace } from '@/api/workspace'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  ModelParamsFields,
  fromApiParams,
  toApiParams,
  type ModelParamsValue,
} from '@/components/ModelParamsFields'
import type { AIModel, ModelParams, Workspace } from '@/types'

interface WorkspaceSettingsPanelProps {
  workspace: Workspace
  /** 保存成功回调（后端返的新 WorkspaceOut），父级覆盖 state → supervisorReady 联动 */
  onSaved: (ws: Workspace) => void
  onClose: () => void
}

interface FormState {
  name: string
  description: string
  model_id: string | null
  params: ModelParamsValue
  system_prompt: string
}

/** workspace → 扁平表单初值（supervisor jsonb 摊平） */
function workspaceToForm(ws: Workspace): FormState {
  const sup = ws.supervisor as {
    models?: { chat?: { id?: string; params?: ModelParams } }
    system_prompt?: string | null
  }
  return {
    name: ws.name,
    description: ws.description,
    model_id: sup.models?.chat?.id ?? null,
    params: fromApiParams(sup.models?.chat?.params),
    system_prompt: sup.system_prompt ?? '',
  }
}

/**
 * 空间配置面板（右栏，与产出物共用一块地、翻转切换）
 *
 * v1 范围：基本信息（名字 / 描述）+ 管家配置（chat 模型 + system_prompt）。
 * workspace 级 config（路由策略 / 开场白 / 共享资源）d-2+ 再露出。
 *
 * 保存 = 一次 updateWorkspace：supervisor 显式构造回 jsonb
 * （不 spread 旧值防 schema 残留，ConfigPanel 同款套路）。
 */
export function WorkspaceSettingsPanel({
  workspace,
  onSaved,
  onClose,
}: WorkspaceSettingsPanelProps) {
  const [form, setForm] = useState<FormState>(() => workspaceToForm(workspace))
  const [chatModels, setChatModels] = useState<AIModel[]>([])
  const [saving, setSaving] = useState(false)

  // 外部 workspace 变化（保存成功覆盖 / 切空间）同步表单
  useEffect(() => {
    setForm(workspaceToForm(workspace))
  }, [workspace])

  useEffect(() => {
    listAllModels({ modelType: 'chat', enabledOnly: true })
      .then(setChatModels)
      .catch(() => {})
  }, [])

  const dirty = useMemo(
    () => JSON.stringify(workspaceToForm(workspace)) !== JSON.stringify(form),
    [workspace, form],
  )

  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const selectedModel = useMemo(
    () => chatModels.find((m) => m.id === form.model_id),
    [chatModels, form.model_id],
  )

  /** 换模型 = 连调用参数一起换成新模型的预设（同 ConfigPanel，理由见那边）。 */
  function selectModel(modelId: string) {
    const preset = chatModels.find((m) => m.id === modelId)?.config
    setForm((prev) => ({
      ...prev,
      model_id: modelId,
      params: fromApiParams(preset as ModelParams | undefined),
    }))
  }

  async function save() {
    const name = form.name.trim()
    if (!name) {
      toast.warning('名字不能为空')
      return
    }
    setSaving(true)
    try {
      const updated = await updateWorkspace(workspace.id, {
        name,
        description: form.description.trim(),
        // 显式构造 supervisor jsonb（AgentConfig 形态），不带 template 键
        supervisor: {
          models: {
            chat: form.model_id
              ? { id: form.model_id, params: toApiParams(form.params) }
              : null,
          },
          system_prompt: form.system_prompt.trim() || null,
        },
      })
      onSaved(updated)
      toast.success('空间配置已保存')
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-background flex h-full min-h-0 flex-col overflow-hidden rounded-lg border shadow-sm">
      {/* 头部 */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-medium">空间配置</h3>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground -mr-1 size-6"
          onClick={onClose}
        >
          <X className="size-3.5" />
        </Button>
      </div>

      {/* 表单（滚动区） */}
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        <div className="space-y-2">
          <Label htmlFor="ws-set-name" className="text-xs font-medium tracking-wide uppercase">
            名字
          </Label>
          <Input
            id="ws-set-name"
            value={form.name}
            onChange={(e) => patch('name', e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="ws-set-desc" className="text-xs font-medium tracking-wide uppercase">
            描述
          </Label>
          <Textarea
            id="ws-set-desc"
            value={form.description}
            placeholder="这个空间用来做什么"
            onChange={(e) => patch('description', e.target.value)}
            className="min-h-16 resize-none"
          />
        </div>

        <Separator />

        <div className="text-muted-foreground flex items-center gap-1.5 text-xs font-medium tracking-wide uppercase">
          <Crown className="text-brand size-3.5" />
          管家配置
        </div>

        <div className="space-y-2">
          <Label className="text-xs font-medium tracking-wide uppercase">对话模型</Label>
          <Select
            value={form.model_id ?? undefined}
            onValueChange={selectModel}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="选择对话模型" />
            </SelectTrigger>
            <SelectContent>
              {chatModels.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <Label className="text-xs font-medium tracking-wide uppercase">调用参数</Label>
          <ModelParamsFields
            value={form.params}
            onChange={(v) => patch('params', v)}
            reasoningLevels={selectedModel?.reasoning_levels}
          />
        </div>

        <div className="space-y-2">
          <Label
            htmlFor="ws-set-prompt"
            className="text-xs font-medium tracking-wide uppercase"
          >
            角色设定
          </Label>
          <Textarea
            id="ws-set-prompt"
            value={form.system_prompt}
            placeholder="管家的角色与行事风格，如：你是这个工作空间的管家，负责协调和回答问题。"
            onChange={(e) => patch('system_prompt', e.target.value)}
            className="min-h-28 resize-none"
          />
        </div>
      </div>

      {/* 底部保存 */}
      <div className="flex shrink-0 items-center justify-between border-t px-4 py-3">
        <span className="text-muted-foreground text-xs">
          {dirty ? <span className="text-warning">● 有未保存改动</span> : '已是最新'}
        </span>
        <Button size="sm" disabled={!dirty || saving} onClick={save}>
          {saving ? '保存中…' : '保存'}
        </Button>
      </div>
    </div>
  )
}
