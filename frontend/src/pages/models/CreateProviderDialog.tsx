import { useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'

import { createProvider, getCredentialDefinitions } from '@/api/model'
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
import type { CredentialField, ProviderType } from '@/types'

const providerTypes: { value: ProviderType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'dashscope', label: '阿里云百炼' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'baidu', label: '百度智能云' },
  { value: 'custom', label: '自定义' },
]

/** provider_type → 默认 base_url */
const defaultBaseUrl: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  siliconflow: 'https://api.siliconflow.cn/v1',
  deepseek: 'https://api.deepseek.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
  baidu: 'https://aip.baidubce.com',
}

/** 兜底字段定义：定义还没拉到时先渲染一个 API Key 框，别让表单空着 */
const FALLBACK_FIELDS: CredentialField[] = [
  { key: 'api_key', label: 'API Key', secret: true, required: false },
]

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
  const [credentials, setCredentials] = useState<Record<string, string>>({})
  const [description, setDescription] = useState('')
  const [revealed, setRevealed] = useState<Record<string, boolean>>({})
  const [submitting, setSubmitting] = useState(false)
  // 全量字段定义，按 provider_type 索引。静态数据，打开对话框时拉一次
  const [definitions, setDefinitions] = useState<Record<string, CredentialField[]>>({})

  useEffect(() => {
    if (!open || Object.keys(definitions).length > 0) return
    getCredentialDefinitions()
      .then(setDefinitions)
      .catch(() => toast.error('凭证字段定义加载失败，表单按默认单 Key 渲染'))
  }, [open, definitions])

  const fields = providerType
    ? (definitions[providerType] ?? FALLBACK_FIELDS)
    : FALLBACK_FIELDS

  // 必填凭证缺一个就不放行——不等后端 400 再告诉用户
  const credentialsFilled = fields.every(
    (f) => !f.required || credentials[f.key]?.trim(),
  )
  const canSubmit =
    name.trim() && providerType && baseUrl.trim() && credentialsFilled

  function handleTypeChange(value: ProviderType) {
    setProviderType(value)
    // 换供应商 = 换凭证形状，已填的字段名对不上了，清掉
    setCredentials({})
    setRevealed({})
    // 自动填充默认 base_url（仅当用户未手动输入时）
    if (!baseUrl || Object.values(defaultBaseUrl).includes(baseUrl)) {
      setBaseUrl(defaultBaseUrl[value] ?? '')
    }
  }

  function resetForm() {
    setName('')
    setProviderType('')
    setBaseUrl('')
    setCredentials({})
    setDescription('')
    setRevealed({})
  }

  async function handleSubmit() {
    if (!canSubmit || !providerType) return
    setSubmitting(true)
    try {
      // 只提交这家认识的字段，且逐个 trim——多余字段后端会直接拒
      const payload = Object.fromEntries(
        fields.map((f) => [f.key, credentials[f.key]?.trim() ?? '']),
      )
      await createProvider({
        name: name.trim(),
        provider_type: providerType,
        base_url: baseUrl.trim(),
        credentials: payload,
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
            配置模型供应商的连接信息，凭证将加密存储
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

          {/* 凭证：字段由后端下发，各供应商不同 */}
          {fields.map((field) => (
            <div key={field.key} className="grid gap-2">
              <Label htmlFor={`provider-cred-${field.key}`}>
                {field.label}
                {field.required && <span className="text-destructive"> *</span>}
              </Label>
              <div className="relative">
                <Input
                  id={`provider-cred-${field.key}`}
                  type={field.secret && !revealed[field.key] ? 'password' : 'text'}
                  placeholder={field.key === 'api_key' ? 'sk-...' : ''}
                  className={field.secret ? 'pr-10' : undefined}
                  value={credentials[field.key] ?? ''}
                  onChange={(e) =>
                    setCredentials((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                />
                {field.secret && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full w-10 hover:bg-transparent"
                    onClick={() =>
                      setRevealed((prev) => ({
                        ...prev,
                        [field.key]: !prev[field.key],
                      }))
                    }
                  >
                    {revealed[field.key] ? (
                      <EyeOff className="size-4 text-muted-foreground" />
                    ) : (
                      <Eye className="size-4 text-muted-foreground" />
                    )}
                  </Button>
                )}
              </div>
            </div>
          ))}

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
