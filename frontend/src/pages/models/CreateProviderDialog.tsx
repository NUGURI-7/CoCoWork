import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'

import { createProvider } from '@/api/model'
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
import { Textarea } from '@/components/ui/textarea'
import type { ProviderType } from '@/types'

const providerTypes: { value: ProviderType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'dashscope', label: '阿里云百炼' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'custom', label: '自定义' },
]

/** provider_type → 默认 base_url */
const defaultBaseUrl: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  siliconflow: 'https://api.siliconflow.cn/v1',
  deepseek: 'https://api.deepseek.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
}

interface CreateProviderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: () => void
}

export function CreateProviderDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateProviderDialogProps) {
  const [name, setName] = useState('')
  const [providerType, setProviderType] = useState<ProviderType | ''>('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [description, setDescription] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = name.trim() && providerType && baseUrl.trim() && apiKey.trim()

  function handleTypeChange(value: ProviderType) {
    setProviderType(value)
    // 自动填充默认 base_url（仅当用户未手动输入时）
    if (!baseUrl || Object.values(defaultBaseUrl).includes(baseUrl)) {
      setBaseUrl(defaultBaseUrl[value] ?? '')
    }
  }

  function resetForm() {
    setName('')
    setProviderType('')
    setBaseUrl('')
    setApiKey('')
    setDescription('')
    setShowKey(false)
  }

  async function handleSubmit() {
    if (!canSubmit || !providerType) return
    setSubmitting(true)
    try {
      await createProvider({
        name: name.trim(),
        provider_type: providerType,
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        description: description.trim(),
      })
      toast.success('供应商创建成功')
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
          <DialogTitle>添加供应商</DialogTitle>
          <DialogDescription>
            配置模型供应商的连接信息，API Key 将加密存储
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* 名称 */}
          <div className="grid gap-2">
            <Label htmlFor="provider-name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="provider-name"
              placeholder="如：阿里云 - 生产"
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* 类型 */}
          <div className="grid gap-2">
            <Label>
              供应商类型 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={providerType}
              onValueChange={(v) => handleTypeChange(v as ProviderType)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择供应商类型" />
              </SelectTrigger>
              <SelectContent>
                {providerTypes.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Base URL */}
          <div className="grid gap-2">
            <Label htmlFor="provider-url">
              Base URL <span className="text-destructive">*</span>
            </Label>
            <Input
              id="provider-url"
              placeholder="https://api.example.com/v1"
              maxLength={512}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>

          {/* API Key */}
          <div className="grid gap-2">
            <Label htmlFor="provider-key">
              API Key <span className="text-destructive">*</span>
            </Label>
            <div className="relative">
              <Input
                id="provider-key"
                type={showKey ? 'text' : 'password'}
                placeholder="sk-..."
                className="pr-10"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-full w-10 hover:bg-transparent"
                onClick={() => setShowKey(!showKey)}
              >
                {showKey ? (
                  <EyeOff className="size-4 text-muted-foreground" />
                ) : (
                  <Eye className="size-4 text-muted-foreground" />
                )}
              </Button>
            </div>
          </div>

          {/* 描述 */}
          <div className="grid gap-2">
            <Label htmlFor="provider-desc">描述</Label>
            <Textarea
              id="provider-desc"
              placeholder="备注信息（可选）"
              maxLength={500}
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
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
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
          >
            {submitting ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
