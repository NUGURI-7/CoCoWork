import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { toast } from 'sonner'

import { createKnowledgeBase } from '@/api/knowledge'
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
import { Textarea } from '@/components/ui/textarea'
import type { AIModel } from '@/types'

/** 切块默认值（见 docs/design/knowledge-rag-v1.md §5；中文 RAG 甜区） */
const DEFAULT_CHUNK_SIZE = '256'
const DEFAULT_OVERLAP = '50'

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
  const [submitting, setSubmitting] = useState(false)
  const [models, setModels] = useState<AIModel[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)

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

  const hasModels = models.length > 0
  const canSubmit = name.trim() && modelId && !submitting

  function resetForm() {
    setName('')
    setDescription('')
    setModelId('')
    setChunkSize(DEFAULT_CHUNK_SIZE)
    setOverlap(DEFAULT_OVERLAP)
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
          chunk_size: Number(chunkSize) || 256,
          overlap: Number(overlap) || 50,
          strategy: 'recursive',
        },
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
