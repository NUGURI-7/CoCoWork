import { useState } from 'react'
import dayjs from 'dayjs'
import { Download, FileText, Inbox, MoreHorizontal, Sparkles, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'

import {
  batchDeleteDocuments,
  batchProcessDocuments,
  deleteDocument,
  getDocumentDownloadUrl,
  triggerProcessDocument,
} from '@/api/knowledge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import type { Document } from '@/types'
import { docStatusMeta, getDocDisplayStatus } from './mock'

interface DocumentListProps {
  kbId: string
  docs: Document[]
  /** 删除成功后回调，父组件用来 refetch 文档列表 */
  onDeleted?: () => void
  /** 触发向量化成功后回调，父组件乐观更新 + 启动轮询 */
  onProcessed?: (docId: string) => void
}

export function DocumentList({ kbId, docs, onDeleted, onProcessed }: DocumentListProps) {
  // 选中态：Set 存选中的 doc id，查/增/删都 O(1)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchConfirmOpen, setBatchConfirmOpen] = useState(false)
  const [batchProcessing, setBatchProcessing] = useState(false)
  const [batchDeleting, setBatchDeleting] = useState(false)

  const allSelected = docs.length > 0 && selected.size === docs.length
  const someSelected = selected.size > 0 && !allSelected

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev) // 复制再改，不原地改 state（React 靠引用变化判断更新）
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected((prev) =>
      prev.size === docs.length ? new Set() : new Set(docs.map((d) => d.id)),
    )
  }

  function clearSelection() {
    setSelected(new Set())
  }

  async function handleBatchProcess() {
    if (batchProcessing) return
    setBatchProcessing(true)
    try {
      const { triggered, skipped } = await batchProcessDocuments(kbId, [...selected])
      // 每个被触发的 doc 复用单个版乐观更新（父级标 processing + 启动轮询）
      triggered.forEach((id) => onProcessed?.(id))
      if (triggered.length) toast.success(`已触发 ${triggered.length} 个文档向量化`)
      if (skipped.length) toast.warning(`${skipped.length} 个文档状态不允许，已跳过`)
      clearSelection()
    } catch {
      // silent，失败不清选中
    } finally {
      setBatchProcessing(false)
    }
  }

  async function handleBatchDelete() {
    setBatchDeleting(true)
    try {
      const { deleted } = await batchDeleteDocuments(kbId, [...selected])
      toast.success(`已删除 ${deleted} 个文档`)
      setBatchConfirmOpen(false)
      clearSelection()
      onDeleted?.()
    } catch {
      // 拦截器已 toast
    } finally {
      setBatchDeleting(false)
    }
  }

  if (docs.length === 0) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-sm">
        <Inbox className="size-8 opacity-40" />
        <p>还没有文档</p>
        <p className="text-xs">点击右上角「上传文档」开始</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* 批量操作栏：选中 ≥1 时浮出 */}
      {selected.size > 0 && (
        <div className="bg-brand-subtle flex items-center gap-2 rounded-lg border px-4 py-2">
          <span className="text-brand text-sm font-medium">已选 {selected.size} 个</span>
          <div className="flex-1" />
          <Button size="sm" variant="outline" disabled={batchProcessing} onClick={handleBatchProcess}>
            <Sparkles className="size-4" />
            批量向量化
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-destructive hover:text-destructive"
            onClick={() => setBatchConfirmOpen(true)}
          >
            <Trash2 className="size-4" />
            批量删除
          </Button>
          <Button size="icon" variant="ghost" className="size-7" onClick={clearSelection}>
            <X className="size-4" />
          </Button>
        </div>
      )}

      <div className="divide-y rounded-lg border">
        {/* 全选行 */}
        <div className="text-muted-foreground flex items-center gap-3 px-4 py-2 text-xs">
          <Checkbox
            checked={allSelected ? true : someSelected ? 'indeterminate' : false}
            onCheckedChange={toggleAll}
            aria-label="全选"
          />
          <span>全选（{docs.length}）</span>
        </div>

        {docs.map((d) => (
          <DocumentRow
            key={d.id}
            kbId={kbId}
            doc={d}
            selected={selected.has(d.id)}
            onToggle={() => toggleOne(d.id)}
            onDeleted={onDeleted}
            onProcessed={onProcessed}
          />
        ))}
      </div>

      {/* 批量删除确认 */}
      <AlertDialog open={batchConfirmOpen} onOpenChange={setBatchConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除选中的 {selected.size} 个文档？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。这些文档及其所有 chunk 与向量将一并清除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchDeleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={batchDeleting}
              onClick={(e) => {
                e.preventDefault()
                handleBatchDelete()
              }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {batchDeleting ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function DocumentRow({
  kbId,
  doc,
  selected,
  onToggle,
  onDeleted,
  onProcessed,
}: {
  kbId: string
  doc: Document
  selected: boolean
  onToggle: () => void
  onDeleted?: () => void
  onProcessed?: (docId: string) => void
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [triggering, setTriggering] = useState(false)

  const display = getDocDisplayStatus(doc)
  const s = docStatusMeta[display]
  const canProcess = display === 'uploaded' || display === 'failed'

  async function handleProcess() {
    if (triggering) return
    setTriggering(true)
    try {
      await triggerProcessDocument(kbId, doc.id)
      toast.success(`已触发「${doc.name}」向量化`)
      onProcessed?.(doc.id)
    } catch {
      // 拦截器已 toast
    } finally {
      setTriggering(false)
    }
  }

  async function handleDownload() {
    if (downloading) return
    setDownloading(true)
    try {
      const { url } = await getDocumentDownloadUrl(kbId, doc.id)
      triggerDownload(url, doc.name)
    } catch {
      // 拦截器已 toast
    } finally {
      setDownloading(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteDocument(kbId, doc.id)
      toast.success(`文档「${doc.name}」已删除`)
      setConfirmOpen(false)
      onDeleted?.()
    } catch {
      // 拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div
        className={cn(
          'flex items-center gap-3 px-4 py-3 transition-colors',
          selected ? 'bg-brand-subtle' : 'hover:bg-muted/40',
        )}
      >
        <Checkbox checked={selected} onCheckedChange={onToggle} aria-label={`选择 ${doc.name}`} />
        <FileText className="text-muted-foreground size-4 shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{doc.name}</div>
          <div className="text-muted-foreground mt-0.5 text-xs">
            {formatBytes(doc.size)} · {doc.chunk_count} chunks
          </div>
        </div>

        <span className="text-muted-foreground hidden items-center gap-1.5 text-xs sm:flex">
          <span className={cn('size-1.5 rounded-full', s.dot, s.pulse && 'animate-pulse')} />
          {s.label}
        </span>

        <span className="text-muted-foreground hidden w-16 text-right text-xs md:block">
          {dayjs(doc.created_at).fromNow()}
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground size-7 shrink-0"
            >
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {canProcess && (
              <DropdownMenuItem onSelect={handleProcess} disabled={triggering}>
                <Sparkles className="size-4" />
                {display === 'failed' ? '重试向量化' : '向量化'}
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={handleDownload} disabled={downloading}>
              <Download className="size-4" />
              下载
            </DropdownMenuItem>
            <DropdownMenuItem
              variant="destructive"
              onSelect={(e) => {
                e.preventDefault()
                setConfirmOpen(true)
              }}
            >
              <Trash2 className="size-4" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除文档「{doc.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。文档的 {doc.chunk_count} 个 chunk 与向量将一并清除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {deleting ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// ---------- helpers ----------

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** 创建临时 `<a download>` 程序触发下载（GitHub/Drive 同款做法） */
function triggerDownload(url: string, filename: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
