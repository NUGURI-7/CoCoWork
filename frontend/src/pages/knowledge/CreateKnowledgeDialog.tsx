import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { toast } from 'sonner'

import { createKnowledgeBase, getParseBackends } from '@/api/knowledge'
import { listAllModels } from '@/api/model'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
  ALL_PARSE_BACKENDS,
  PARSE_BACKEND_HINTS,
  PARSE_BACKEND_LABELS,
  type AIModel,
  type ParseBackend,
} from '@/types'

/** 切块默认值。单位是 token（cl100k_base 口径），中文一字约 1.14 token，
 *  故 256 折合约 225 个汉字。与后端 ChunkConfig 的默认值保持一致 */
const DEFAULT_CHUNK_SIZE = '256'
const DEFAULT_OVERLAP = '20'
/** 与后端 ChunkConfig.prepend_title 的默认值保持一致 */
const DEFAULT_PREPEND_TITLE = true

interface CreateKnowledgeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 创建成功回调（用于父组件 refetch 列表） */
  onCreated?: () => void
}

export function CreateKnowledgeDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateKnowledgeDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [modelId, setModelId] = useState('')
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNK_SIZE)
  const [overlap, setOverlap] = useState(DEFAULT_OVERLAP)
  const [prependTitle, setPrependTitle] = useState(DEFAULT_PREPEND_TITLE)
  const [submitting, setSubmitting] = useState(false)
  const [models, setModels] = useState<AIModel[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [parseBackend, setParseBackend] = useState<ParseBackend>('local')
  const [availableBackends, setAvailableBackends] = useState<ParseBackend[]>(['local'])

  // 打开时拉取可用的 embedding 模型（后端 list_own 天然只返回当前用户的模型）
  useEffect(() => {
    if (!open) return
    setModelsLoading(true)
    listAllModels({ modelType: 'embedding', enabledOnly: true })
      .then(setModels)
      .catch(() => {
        // 拦截器已 toast；下拉降级为空态
      })
      .finally(() => setModelsLoading(false))
  }, [open])

  // 解析后端可选项取决于部署侧配没配 Key，前端看不见，只能问后端。
  // 失败时退回只有 local —— 那条路零配置永远可用，不会把人挡在建库之外
  useEffect(() => {
    if (!open) return
    getParseBackends()
      .then(setAvailableBackends)
      .catch(() => setAvailableBackends(['local']))
  }, [open])

  const hasModels = models.length > 0
  const canSubmit = name.trim() && modelId && !submitting

  function resetForm() {
    setName('')
    setDescription('')
    setModelId('')
    setChunkSize(DEFAULT_CHUNK_SIZE)
    setOverlap(DEFAULT_OVERLAP)
    setPrependTitle(DEFAULT_PREPEND_TITLE)
    setParseBackend('local')
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      await createKnowledgeBase({
        name: name.trim(),
        description: description.trim() || undefined,
        embedding_model_id: modelId,
        chunk_config: {
          chunk_size: Number(chunkSize) || Number(DEFAULT_CHUNK_SIZE),
          overlap: Number(overlap) || Number(DEFAULT_OVERLAP),
          prepend_title: prependTitle,
        },
        parse_backend: parseBackend,
      })
      toast.success('知识库创建成功')
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
          <DialogTitle>新建知识库</DialogTitle>
          <DialogDescription>
            创建后将锁定 embedding 模型，用于文档向量化与检索
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* 名称 */}
          <div className="grid gap-2">
            <Label htmlFor="kb-name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="kb-name"
              placeholder="如：产品文档库"
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* 描述 */}
          <div className="grid gap-2">
            <Label htmlFor="kb-description">描述</Label>
            <Textarea
              id="kb-description"
              placeholder="简要说明这个知识库的用途（可选）"
              rows={2}
              maxLength={500}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Embedding 模型 */}
          <div className="grid gap-2">
            <Label>
              Embedding 模型 <span className="text-destructive">*</span>
            </Label>
            <Select value={modelId} onValueChange={setModelId} disabled={!hasModels}>
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    modelsLoading
                      ? '加载中…'
                      : hasModels
                        ? '选择向量模型'
                        : '暂无可用的向量模型'
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {models.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    <span>{m.display_name}</span>
                    <span className="text-muted-foreground ml-2 font-mono text-xs">
                      {m.model_name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!modelsLoading && !hasModels ? (
              <p className="text-muted-foreground text-xs">
                还没有 embedding 模型，先去{' '}
                <Link
                  to="/models"
                  className="text-brand hover:underline"
                  onClick={() => onOpenChange(false)}
                >
                  模型模块
                </Link>{' '}
                接入一个向量模型。
              </p>
            ) : (
              <p className="text-muted-foreground text-xs">
                建库后更换模型需重新向量化全部文档
              </p>
            )}
          </div>

          {/* 文档解析后端 —— 只对 PDF 有差别，md / txt 两条路结果一致 */}
          <div className="grid gap-2">
            <Label>PDF 解析方式</Label>
            <Select
              value={parseBackend}
              onValueChange={(v) => setParseBackend(v as ParseBackend)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ALL_PARSE_BACKENDS.map((backend) => {
                  const usable = availableBackends.includes(backend)
                  return (
                    <SelectItem key={backend} value={backend} disabled={!usable}>
                      <span>{PARSE_BACKEND_LABELS[backend]}</span>
                      {!usable && (
                        <span className="text-muted-foreground ml-2 text-xs">
                          未配置凭证
                        </span>
                      )}
                    </SelectItem>
                  )
                })}
              </SelectContent>
            </Select>
            <p className="text-muted-foreground text-xs">
              {PARSE_BACKEND_HINTS[parseBackend]}
            </p>
          </div>

          {/* 高级：切块配置 */}
          <Accordion type="single" collapsible>
            <AccordionItem value="advanced" className="border-b-0">
              <AccordionTrigger className="py-2 text-sm">
                高级 · 切块配置
              </AccordionTrigger>
              <AccordionContent className="grid grid-cols-2 gap-4 pt-1">
                <div className="grid gap-2">
                  <Label htmlFor="kb-chunk-size" className="text-xs">
                    Chunk Size (token)
                  </Label>
                  <Input
                    id="kb-chunk-size"
                    type="number"
                    min={64}
                    max={2048}
                    placeholder={DEFAULT_CHUNK_SIZE}
                    value={chunkSize}
                    onChange={(e) => setChunkSize(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="kb-overlap" className="text-xs">
                    Overlap (token)
                  </Label>
                  <Input
                    id="kb-overlap"
                    type="number"
                    min={0}
                    max={512}
                    placeholder={DEFAULT_OVERLAP}
                    value={overlap}
                    onChange={(e) => setOverlap(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="col-span-2 flex items-start justify-between gap-4 rounded-md border p-3">
                  <div className="grid gap-1">
                    <Label htmlFor="kb-prepend-title" className="text-xs">
                      标题链前置
                    </Label>
                    <p className="text-muted-foreground text-xs">
                      向量化前给每个子块补上「第三章 &gt; 3.2 报销流程」这样的所属层级，
                      避免「不超过 30 天」这类脱离上下文就检索不到的片段。
                      标题本身没什么信息量的文档（全是「第一节」「第二节」）建议关掉。
                    </p>
                  </div>
                  <Switch
                    id="kb-prepend-title"
                    checked={prependTitle}
                    onCheckedChange={setPrependTitle}
                  />
                </div>
                <p className="text-muted-foreground col-span-2 text-xs">
                  切分策略：递归切分（默认）。更小的子块检索更精准，命中后返回所属整段补充上下文。
                </p>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? '创建中…' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
