import { useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'

import {
  createProvider,
  getCredentialDefinitions,
  updateProvider,
  type ProviderUpdatePayload,
} from '@/api/model'
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
import type { CredentialField, Provider, ProviderType } from '@/types'

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

/** 兜底字段定义：定义还没拉到时先渲染一个 API Key 框，别让表单空着 */
const FALLBACK_FIELDS: CredentialField[] = [
  { key: 'api_key', label: 'API Key', secret: true, required: false },
]

interface ProviderFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 给了就是编辑模式，不给就是新建 */
  provider?: Provider
  /** 新建成功 / 编辑保存成功都走它 —— 调用方只需要「刷新列表」这一个动作 */
  onSaved?: () => void
}

/**
 * Provider 新建 / 编辑对话框（同一份表单两用）。
 *
 * **凭证在编辑模式下是空的**：后端只存密文、从不回传，所以这里没法预填。
 * 留空 = 不动原凭证（payload 里干脆不带 credentials 字段），填了才整包替换。
 */
export function ProviderFormDialog({
  open,
  onOpenChange,
  provider,
  onSaved,
}: ProviderFormDialogProps) {
  const isEdit = !!provider
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

  // 编辑模式：每次打开都按当前 provider 重铺一遍表单，避免上一次的残留
  useEffect(() => {
    if (!open || !provider) return
    setName(provider.name)
    setProviderType(provider.provider_type)
    setBaseUrl(provider.base_url)
    setDescription(provider.description ?? '')
    setCredentials({})
    setRevealed({})
  }, [open, provider])

  const fields = providerType
    ? (definitions[providerType] ?? FALLBACK_FIELDS)
    : FALLBACK_FIELDS

  // 编辑时换了供应商类型 —— 原凭证是按旧类型的字段存的，形状对不上，必须重填
  const typeChanged = !!provider && providerType !== provider.provider_type

  // 必填凭证缺一个就不放行——不等后端 400 再告诉用户。
  // 编辑且没换类型时豁免：留空 = 沿用原凭证，不是没填。
  // 换了类型则按新类型的字段定义重新把关（该类型不要求 key，就一个都不用填）。
  const credentialsFilled =
    (isEdit && !typeChanged) ||
    fields.every((f) => !f.required || credentials[f.key]?.trim())
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
      const creds = Object.fromEntries(
        fields.map((f) => [f.key, credentials[f.key]?.trim() ?? '']),
      )
      if (provider) {
        const payload: ProviderUpdatePayload = {
          name: name.trim(),
          provider_type: providerType,
          base_url: baseUrl.trim(),
          description: description.trim(),
        }
        // 换了类型 → 无条件整包替换（哪怕全空）：旧类型的凭证字段形状对不上新类型，
        //   留着就是一份读不懂的脏数据；本来就不需要 key 的供应商，空包正是它该有的样子。
        // 没换类型 → 一个都没填代表沿用原凭证，此时绝不能带这个字段（带了 = 拿空串洗掉密文）。
        if (typeChanged || Object.values(creds).some((v) => v)) {
          payload.credentials = creds
        }
        await updateProvider(provider.id, payload)
        toast.success('供应商已更新')
      } else {
        await createProvider({
          name: name.trim(),
          provider_type: providerType,
          base_url: baseUrl.trim(),
          credentials: creds,
          description: description.trim(),
        })
        toast.success('供应商创建成功')
      }
      resetForm()
      onOpenChange(false)
      onSaved?.()
    } catch (err) {
      const msg = err instanceof Error ? err.message : isEdit ? '保存失败' : '创建失败'
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
          <DialogTitle>{isEdit ? '编辑供应商' : '添加供应商'}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? '凭证留空则沿用原来的，填了才整包替换'
              : '配置模型供应商的连接信息，凭证将加密存储'}
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
                  placeholder={
                    typeChanged
                      ? '换了类型，按新类型填（不需要就留空）'
                      : isEdit
                        ? '留空则不修改'
                        : field.key === 'api_key'
                          ? 'sk-...'
                          : ''
                  }
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

          {typeChanged && (
            <p className="text-warning text-xs">
              已切换供应商类型，原凭证不再适用，保存时将按上面填的内容整包替换（不填即清空）。
            </p>
          )}

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
            {submitting
              ? isEdit
                ? '保存中...'
                : '创建中...'
              : isEdit
                ? '保存'
                : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
