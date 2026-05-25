import { useEffect, useRef, useState } from 'react'
import {
  CheckCircle2,
  FileText,
  Upload,
  UploadCloud,
  X,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import type { DocType, KnowledgeDoc } from './mock'

/** v1 仅支持纯文本（见 docs/design/knowledge-rag-v1.md §1） */
const ACCEPT = '.md,.txt'
const ACCEPTED_EXTS: string[] = ['md', 'txt']
/** mock 阶段文件大小上限（10 MB） */
const MAX_BYTES = 10 * 1024 * 1024

type QueueStatus = 'pending' | 'uploading' | 'done' | 'failed'

interface QueueItem {
  id: string
  file: File
  ext: DocType
  progress: number
  status: QueueStatus
  error?: string
}

interface UploadDocumentSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kbId: string
  onUploaded?: (docs: KnowledgeDoc[]) => void
}

export function UploadDocumentSheet({
  open,
  onOpenChange,
  kbId,
  onUploaded,
}: UploadDocumentSheetProps) {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // 关闭时重置
  useEffect(() => {
    if (!open) {
      setQueue([])
      setDragOver(false)
    }
  }, [open])

  const uploading = queue.some((q) => q.status === 'uploading')
  const allDone =
    queue.length > 0 && queue.every((q) => q.status === 'done' || q.status === 'failed')
  const canUpload =
    queue.length > 0 && queue.some((q) => q.status === 'pending') && !uploading

  function addFiles(files: FileList | File[]) {
    const arr = Array.from(files)
    const next: QueueItem[] = []
    for (const file of arr) {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
      if (!ACCEPTED_EXTS.includes(ext)) {
        toast.error(`「${file.name}」不支持的类型，仅 MD / TXT`)
        continue
      }
      if (file.size > MAX_BYTES) {
        toast.error(`「${file.name}」超过 10 MB 上限`)
        continue
      }
      next.push({
        id: crypto.randomUUID(),
        file,
        ext: ext as DocType,
        progress: 0,
        status: 'pending',
      })
    }
    if (next.length) setQueue((prev) => [...prev, ...next])
  }

  function removeItem(id: string) {
    setQueue((prev) => prev.filter((q) => q.id !== id))
  }

  /** mock 上传：每个 pending 文件用 setInterval 推进度到 100% */
  function startUpload() {
    setQueue((prev) =>
      prev.map((q) => (q.status === 'pending' ? { ...q, status: 'uploading' } : q)),
    )
    queue
      .filter((q) => q.status === 'pending')
      .forEach((item) => {
        const timer = setInterval(() => {
          setQueue((prev) => {
            const cur = prev.find((q) => q.id === item.id)
            if (!cur || cur.status !== 'uploading') {
              clearInterval(timer)
              return prev
            }
            const nextProgress = Math.min(100, cur.progress + 20)
            const nextStatus: QueueStatus = nextProgress >= 100 ? 'done' : 'uploading'
            if (nextProgress >= 100) clearInterval(timer)
            return prev.map((q) =>
              q.id === item.id ? { ...q, progress: nextProgress, status: nextStatus } : q,
            )
          })
        }, 120)
      })
  }

  function handleFinish() {
    const docs: KnowledgeDoc[] = queue
      .filter((q) => q.status === 'done')
      .map((q) => ({
        id: crypto.randomUUID(),
        kb_id: kbId,
        name: q.file.name,
        type: q.ext,
        size: formatBytes(q.file.size),
        chunk_count: 0,
        // spec §3.2 上传后 status=pending（未向量化）；前端 mock 枚举无 pending，
        // 用 processing 表达「正在处理」更直观
        status: 'processing',
        uploaded_at: '刚刚',
      }))
    if (docs.length) {
      toast.success(`已添加 ${docs.length} 篇文档，等待向量化`)
      onUploaded?.(docs)
    }
    onOpenChange(false)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>上传文档</SheetTitle>
          <SheetDescription>
            支持 MD / TXT，单文件最大 10 MB。上传后将进入待向量化队列。
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 pb-4">
          {/* 拖拽框 */}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
            }}
            className={cn(
              'flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-10 text-sm transition-colors',
              dragOver
                ? 'border-brand bg-brand-subtle text-brand'
                : 'border-border/70 text-muted-foreground hover:border-brand hover:text-brand',
            )}
          >
            <UploadCloud className="size-7 opacity-80" />
            <p>
              <span className="text-foreground font-medium">点击选择</span> 或 拖拽文件到这里
            </p>
            <p className="text-xs opacity-70">仅支持 MD / TXT</p>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files?.length) addFiles(e.target.files)
              e.target.value = '' // 允许重复选同一文件
            }}
          />

          {/* 文件队列 */}
          {queue.length > 0 && (
            <div className="space-y-2">
              <div className="text-muted-foreground text-xs">
                文件队列 · {queue.length}
              </div>
              <div className="divide-y rounded-lg border">
                {queue.map((q) => (
                  <QueueRow key={q.id} item={q} onRemove={() => removeItem(q.id)} />
                ))}
              </div>
            </div>
          )}
        </div>

        <SheetFooter className="border-t">
          {!allDone ? (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={uploading}
              >
                取消
              </Button>
              <Button onClick={startUpload} disabled={!canUpload}>
                <Upload className="size-4" />
                {uploading ? '上传中…' : `上传 ${queue.filter((q) => q.status === 'pending').length} 个文件`}
              </Button>
            </>
          ) : (
            <Button onClick={handleFinish}>完成</Button>
          )}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

// ---------- 内部组件 ----------

function QueueRow({
  item,
  onRemove,
}: {
  item: QueueItem
  onRemove: () => void
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5">
      <FileText className="text-muted-foreground size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm">{item.file.name}</div>
        <div className="mt-1 flex items-center gap-2">
          <div className="bg-muted h-1 flex-1 overflow-hidden rounded-full">
            <div
              className={cn(
                'h-full transition-all',
                item.status === 'failed' ? 'bg-destructive' : 'bg-brand',
              )}
              style={{ width: `${item.progress}%` }}
            />
          </div>
          <span className="text-muted-foreground w-16 shrink-0 text-right text-xs tabular-nums">
            {formatBytes(item.file.size)}
          </span>
        </div>
      </div>
      <StatusIcon status={item.status} onRemove={onRemove} />
    </div>
  )
}

function StatusIcon({
  status,
  onRemove,
}: {
  status: QueueStatus
  onRemove: () => void
}) {
  if (status === 'done') {
    return <CheckCircle2 className="text-success size-4 shrink-0" />
  }
  if (status === 'failed') {
    return <XCircle className="text-destructive size-4 shrink-0" />
  }
  // pending / uploading 都能移除（uploading 中点移除等于取消该项的后续推进）
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-6 shrink-0"
      onClick={onRemove}
      aria-label="移除"
    >
      <X className="size-3.5" />
    </Button>
  )
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
