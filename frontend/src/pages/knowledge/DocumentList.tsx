import { useState } from 'react'
import dayjs from 'dayjs'
import { Download, FileText, Inbox, MoreHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { deleteDocument, getDocumentDownloadUrl } from '@/api/knowledge'
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
}

export function DocumentList({ kbId, docs, onDeleted }: DocumentListProps) {
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
    <div className="divide-y rounded-lg border">
      {docs.map((d) => (
        <DocumentRow key={d.id} kbId={kbId} doc={d} onDeleted={onDeleted} />
      ))}
    </div>
  )
}

function DocumentRow({
  kbId,
  doc,
  onDeleted,
}: {
  kbId: string
  doc: Document
  onDeleted?: () => void
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const display = getDocDisplayStatus(doc)
  const s = docStatusMeta[display]

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
      <div className="hover:bg-muted/40 flex items-center gap-3 px-4 py-3 transition-colors">
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
  // 同源时 download 属性生效；跨域时由响应头 Content-Disposition: attachment 接管
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
