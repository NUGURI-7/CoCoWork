import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { createModel, getParamDefinitions } from '@/api/model'
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
import { Separator } from '@/components/ui/separator'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import type { ModelType, ModelTypeParams, ParamField } from '@/types'

/** 模型类型 → 中文标签 */
const modelTypeLabel: Record<string, string> = {
  chat: '对话模型',
  embedding: '向量模型',
  rerank: '重排序模型',
  vision: '视觉模型',
  tts: '语音合成',
  stt: '语音识别',
  image: '图像生成',
  multimodal: '多模态',
}

interface CreateModelDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  providerId: string
  modelName: string
  modelType: ModelType
  onCreated?: () => void
}

/** 渲染单个参数控件 */
function ParamControl({
  field,
  value,
  onChange,
}: {
  field: ParamField
  value: number | boolean | null | undefined
  onChange: (val: number | boolean | null) => void
}) {
  if (field.type === 'slider') {
    const num = typeof value === 'number' ? value : (field.default as number) ?? 0
    return (
      <div className="grid gap-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">{field.label}</Label>
          <span className="text-muted-foreground text-xs tabular-nums">{num}</span>
        </div>
        <Slider
          min={field.min ?? 0}
          max={field.max ?? 1}
          step={field.step ?? 0.1}
          value={[num]}
          onValueChange={([v]) => onChange(v)}
        />
      </div>
    )
  }

  if (field.type === 'switch') {
    const bool = typeof value === 'boolean' ? value : (field.default as boolean) ?? false
    return (
      <div className="flex items-center justify-between">
        <Label className="text-xs">{field.label}</Label>
        <Switch checked={bool} onCheckedChange={(v) => onChange(v)} />
      </div>
    )
  }

  // number
  return (
    <div className="grid gap-2">
      <Label className="text-xs">
        {field.label}
        {field.description && (
          <span className="text-muted-foreground ml-1 font-normal">
            ({field.description})
          </span>
        )}
      </Label>
      <Input
        type="number"
        min={field.min ?? undefined}
        max={field.max ?? undefined}
        step={field.step ?? undefined}
        placeholder={field.default != null ? String(field.default) : ''}
        value={value != null ? String(value) : ''}
        onChange={(e) => {
          const v = e.target.value
          onChange(v === '' ? null : Number(v))
        }}
        className="h-8 text-xs"
      />
    </div>
  )
}

export function CreateModelDialog({
  open,
  onOpenChange,
  providerId,
  modelName,
  modelType,
  onCreated,
}: CreateModelDialogProps) {
  const [displayName, setDisplayName] = useState('')
  const [config, setConfig] = useState<Record<string, number | boolean | null>>({})
  const [submitting, setSubmitting] = useState(false)
  const [paramDefs, setParamDefs] = useState<Record<string, ModelTypeParams>>({})

  // 参数定义是全局静态元数据，挂载时拉一次
  useEffect(() => {
    getParamDefinitions()
      .then(setParamDefs)
      .catch(() => {
        // 拦截器已 toast；参数区降级为空
      })
  }, [])

  const paramDef = paramDefs[modelType]
  const invocationParams = paramDef?.invocation_params ?? []

  const canSubmit = displayName.trim()

  function resetForm() {
    setDisplayName('')
    setConfig({})
  }

  function updateConfig(key: string, val: number | boolean | null) {
    setConfig((prev) => ({ ...prev, [key]: val }))
  }

  /** 构建 config 对象：只提交用户修改过的值 */
  function buildConfig() {
    const result: Record<string, unknown> = {}
    for (const field of invocationParams) {
      const val = config[field.key]
      if (val != null) {
        result[field.key] = val
      }
    }
    return result
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      await createModel(providerId, {
        model_name: modelName,
        display_name: displayName.trim(),
        model_type: modelType,
        config: buildConfig(),
        is_enabled: true,
      })
      toast.success('模型创建成功')
      resetForm()
      onOpenChange(false)
      onCreated?.()
    } catch (err) {
      const msg = err instanceof Error ? err.message : '创建失败'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) resetForm()
        onOpenChange(v)
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>创建模型</DialogTitle>
          <DialogDescription>
            基于 <code className="bg-muted rounded px-1 text-xs">{modelName}</code> 创建模型实例
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* 模型信息（只读） */}
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label className="text-muted-foreground text-xs">上游模型</Label>
              <p className="truncate font-mono text-sm">{modelName}</p>
            </div>
            <div className="grid gap-1.5">
              <Label className="text-muted-foreground text-xs">类型</Label>
              <p className="text-sm">{modelTypeLabel[modelType] ?? modelType}</p>
            </div>
          </div>

          {/* 展示名 */}
          <div className="grid gap-2">
            <Label htmlFor="model-display-name">
              展示名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="model-display-name"
              placeholder="如：Qwen Turbo"
              maxLength={100}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>

          {/* 调用参数 */}
          {invocationParams.length > 0 && (
            <>
              <Separator />
              <div className="space-y-3">
                <Label className="text-muted-foreground text-xs font-normal">
                  调用参数预设（可选）
                </Label>
                {invocationParams.map((field) => (
                  <ParamControl
                    key={field.key}
                    field={field}
                    value={config[field.key]}
                    onChange={(v) => updateConfig(field.key, v)}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || submitting}>
            {submitting ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
