import { useState } from 'react'
import { Download, FileText, Inbox, MoreHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

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
import { docStatusMeta, type KnowledgeDoc } from './mock'

interface DocumentListProps {
  docs: KnowledgeDoc[]
  /** 传入则三点菜单的「删除」启用；不传则 disabled */
  onDelete?: (id: string) => void
}

export function DocumentList({ docs, onDelete }: DocumentListProps) {
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
        <DocumentRow key={d.id} doc={d} onDelete={onDelete} />
      ))}
    </div>
  )
}

function DocumentRow({
  doc,
  onDelete,
}: {
  doc: KnowledgeDoc
  onDelete?: (id: string) => void
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const s = docStatusMeta[doc.status]

  function handleDownload() {
    toast.info('下载功能等后端接入')
  }

  function handleDelete() {
    onDelete?.(doc.id)
    toast.success(`文档「${doc.name}」已删除`)
    setConfirmOpen(false)
  }

  return (
    <>
      <div className="hover:bg-muted/40 flex items-center gap-3 px-4 py-3 transition-colors">
        <FileText className="text-muted-foreground size-4 shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{doc.name}</div>
          <div className="text-muted-foreground mt-0.5 text-xs">
            {doc.size} · {doc.chunk_count} chunks
          </div>
        </div>

        <span className="text-muted-foreground hidden items-center gap-1.5 text-xs sm:flex">
          <span className={cn('size-1.5 rounded-full', s.dot, s.pulse && 'animate-pulse')} />
          {s.label}
        </span>

        <span className="text-muted-foreground hidden w-14 text-right text-xs md:block">
          {doc.uploaded_at}
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
            <DropdownMenuItem onSelect={handleDownload}>
              <Download className="size-4" />
              下载
            </DropdownMenuItem>
            <DropdownMenuItem
              variant="destructive"
              disabled={!onDelete}
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
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
