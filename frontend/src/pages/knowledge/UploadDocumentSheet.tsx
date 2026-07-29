import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileText, Upload, UploadCloud, X, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { v4 as uuidv4 } from 'uuid'
import {
  confirmDocumentUpload,
  initDocumentUpload,
  uploadDocumentPassthrough,
  uploadDocumentToR2,
} from '@/api/knowledge'
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

/** 跟后端 ALLOWED_FILE_TYPES 对齐（backend/app/schemas/knowledge/document_schema.py） */
const ACCEPT = '.md,.txt,.pdf'
const ACCEPTED_EXTS = ['md', 'txt', 'pdf'] as const
type AllowedExt = (typeof ACCEPTED_EXTS)[number]
/** 跟后端 STORAGE_MAX_UPLOAD_SIZE 对齐（50 MB） */
const MAX_BYTES = 50 * 1024 * 1024

type QueueStatus = 'pending' | 'uploading' | 'done' | 'failed'

interface QueueItem {
  id: string
  file: File
  ext: AllowedExt
  progress: number
  status: QueueStatus
  error?: string
}

interface UploadDocumentSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kbId: string
  /** 上传完成（不论几个、有失败的也算）回调，父组件用来 refetch 文档列表 */
  onUploaded?: () => void
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
  const canUpload = queue.length > 0 && queue.some((q) => q.status === 'pending') && !uploading

  function addFiles(files: FileList | File[]) {
    const arr = Array.from(files)
    const next: QueueItem[] = []
    for (const file of arr) {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
      if (!ACCEPTED_EXTS.includes(ext as AllowedExt)) {
        toast.error(`「${file.name}」不支持的类型，仅 MD / TXT / PDF`)
        continue
      }
      if (file.size > MAX_BYTES) {
        toast.error(`「${file.name}」超过 50 MB 上限`)
        continue
      }
      next.push({
        id: uuidv4(),
        file,
        ext: ext as AllowedExt,
        progress: 0,
        status: 'pending',
      })
    }
    if (next.length) setQueue((prev) => [...prev, ...next])
  }

  function removeItem(id: string) {
    setQueue((prev) => prev.filter((q) => q.id !== id))
  }

  /** 单文件完整上传流程：init → 上传字节 →（R2 才有）confirm。任一步抛错传播给上游。 */
  async function uploadOne(item: QueueItem, onProgress: (ratio: number) => void): Promise<void> {
    // 1. init：建 pending document、按 backend 返不同 strategy
    const init = await initDocumentUpload(kbId, {
      name: item.file.name,
      size: item.file.size,
    })

    // 2. 传字节流（按 strategy 分流）
    if (init.strategy === 'presign') {
      // R2 模式：先 PUT R2 → 完事调 complete 通知后端确认
      await uploadDocumentToR2(init.upload_url!, item.file, init.headers, onProgress)
      await confirmDocumentUpload(kbId, init.document_id)
    } else {
      // Local 模式：multipart POST 给后端，后端落盘 + 自动 mark uploaded，不用 confirm
      await uploadDocumentPassthrough(init.upload_endpoint!, item.file, onProgress)
    }
  }

  async function startUpload() {
    // 一次性把所有 pending 标 uploading（UI 立刻反映"开始了"）
    setQueue((prev) =>
      prev.map((q) => (q.status === 'pending' ? { ...q, status: 'uploading' } : q)),
    )

    // 拿这一刻的 pending 文件 snapshot（基于闭包里的 queue，后续 setState 异步不影响）
    const pendingItems = queue.filter((q) => q.status === 'pending')

    // 并发上传：每个文件独立、单个失败不影响其他，所以用 allSettled 而非 all
    await Promise.allSettled(
      pendingItems.map((item) =>
        uploadOne(item, (ratio) => {
          // 进度回调：用函数形式 setState，永远基于最新 prev 改这一项
          setQueue((prev) =>
            prev.map((q) => (q.id === item.id ? { ...q, progress: Math.round(ratio * 100) } : q)),
          )
        })
          .then(() => {
            // 成功：进度钉死 100、状态置 done
            setQueue((prev) =>
              prev.map((q) => (q.id === item.id ? { ...q, progress: 100, status: 'done' } : q)),
            )
          })
          .catch((err) => {
            // 失败：记 error message + 状态置 failed
            const msg = err instanceof Error ? err.message : '上传失败'
            setQueue((prev) =>
              prev.map((q) => (q.id === item.id ? { ...q, status: 'failed', error: msg } : q)),
            )
          }),
      ),
    )
  }

  function handleFinish() {
    const doneCount = queue.filter((q) => q.status === 'done').length
    if (doneCount > 0) {
      toast.success(`已添加 ${doneCount} 篇文档，等待向量化`)
      onUploaded?.()
    }
    onOpenChange(false)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>上传文档</SheetTitle>
          <SheetDescription>
            支持 MD / TXT / PDF，单文件最大 50 MB。上传后将进入待向量化队列。
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
            <p className="text-xs opacity-70">仅支持 MD / TXT / PDF</p>
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
              <div className="text-muted-foreground text-xs">文件队列 · {queue.length}</div>
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
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={uploading}>
                取消
              </Button>
              <Button onClick={startUpload} disabled={!canUpload}>
                <Upload className="size-4" />
                {uploading
                  ? '上传中…'
                  : `上传 ${queue.filter((q) => q.status === 'pending').length} 个文件`}
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

function QueueRow({ item, onRemove }: { item: QueueItem; onRemove: () => void }) {
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

function StatusIcon({ status, onRemove }: { status: QueueStatus; onRemove: () => void }) {
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
