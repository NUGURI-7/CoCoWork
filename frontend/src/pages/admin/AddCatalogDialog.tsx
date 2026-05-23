import { useState } from 'react'
import { toast } from 'sonner'

import { createCatalog } from '@/api/model'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ModelType, ProviderType } from '@/types'

const providerTypeOptions: { value: ProviderType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'dashscope', label: '阿里云百炼' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'custom', label: '自定义' },
]

const modelTypeOptions: { value: ModelType; label: string }[] = [
  { value: 'chat', label: '对话' },
  { value: 'embedding', label: '向量' },
  { value: 'rerank', label: '重排序' },
]

interface AddCatalogDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: () => void
}

export function AddCatalogDialog({
  open,
  onOpenChange,
  onCreated,
}: AddCatalogDialogProps) {
  const [providerType, setProviderType] = useState<ProviderType | ''>('')
  const [modelType, setModelType] = useState<ModelType | ''>('')
  const [modelId, setModelId] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = providerType && modelType && modelId.trim()

  function resetForm() {
    setProviderType('')
    setModelType('')
    setModelId('')
  }

  async function handleSubmit() {
    if (!canSubmit || !providerType || !modelType) return
    setSubmitting(true)
    try {
      await createCatalog({
        provider_type: providerType,
        model_type: modelType,
        model_id: modelId.trim(),
      })
      toast.success('目录条目已添加')
      resetForm()
      onOpenChange(false)
      onCreated?.()
    } catch (err) {
      const msg = err instanceof Error ? err.message : '添加失败'
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
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>添加目录条目</DialogTitle>
          <DialogDescription>
            登记一个上游可用模型，供用户创建模型时选用
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>
              供应商类型 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={providerType}
              onValueChange={(v) => setProviderType(v as ProviderType)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择供应商类型" />
              </SelectTrigger>
              <SelectContent>
                {providerTypeOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label>
              模型类型 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={modelType}
              onValueChange={(v) => setModelType(v as ModelType)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择模型类型" />
              </SelectTrigger>
              <SelectContent>
                {modelTypeOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="catalog-model-id">
              模型 ID <span className="text-destructive">*</span>
            </Label>
            <Input
              id="catalog-model-id"
              placeholder="如：gpt-4o-mini"
              maxLength={100}
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            />
          </div>
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
            {submitting ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
