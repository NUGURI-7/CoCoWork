import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { BookOpen, Layers, MoreHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { deleteKnowledgeBase } from '@/api/knowledge'
import { cn } from '@/lib/utils'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { KnowledgeBase } from '@/types'
import { kbStatusMeta } from './mock'

interface KnowledgeCardProps {
  kb: KnowledgeBase
  onDeleted?: () => void
}

export function KnowledgeCard({ kb, onDeleted }: KnowledgeCardProps) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const s = kbStatusMeta[kb.status]

  function handleClick() {
    navigate({ to: '/knowledge/$kbId', params: { kbId: kb.id } })
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteKnowledgeBase(kb.id)
      toast.success(`知识库「${kb.name}」已删除`)
      // 关掉本库详情标签（若开着），避免残留死链
      useWorkspaceTabsStore.getState().close(`/knowledge/${kb.id}`)
      setConfirmOpen(false)
      onDeleted?.()
    } catch {
      // 删除非 silent，失败拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Card className="card-interactive gap-0 py-0" onClick={handleClick}>
        <CardContent className="flex flex-col gap-4 p-5">
          {/* 标题区 */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <div className="bg-brand-subtle flex size-10 shrink-0 items-center justify-center rounded-lg">
                <BookOpen className="text-brand size-5" />
              </div>
              <div className="min-w-0">
                <h3 className="truncate font-medium">{kb.name}</h3>
                <p className="text-muted-foreground mt-0.5 line-clamp-1 text-sm">
                  {kb.description}
                </p>
              </div>
            </div>
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-foreground -mr-1 -mt-1 size-6"
                  >
                    <MoreHorizontal className="size-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
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
          </div>

          <Separator />

          {/* 数据区：左 状态 / embedding badge 上下两行 | 右 数字
           * badge 独占一行而非跟状态挤同一行 —— 模型名可以很长（BAAI/bge-large-zh-v1.5），
           * 同行时会把右侧数字顶穿；truncate + max-w-full 再兜一层更长的名字。 */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col items-start gap-2">
              <span className="text-muted-foreground flex shrink-0 items-center gap-1.5 text-xs">
                <span className={cn('size-2 rounded-full', s.dot, s.pulse && 'animate-pulse')} />
                {s.label}
              </span>
              <Badge variant="secondary" className="max-w-full gap-1">
                <Layers />
                <span className="truncate">{kb.embedding_model_name}</span>
              </Badge>
            </div>
            <div className="flex shrink-0 gap-5">
              <div className="text-right">
                <div className="font-mono text-xl leading-none tabular-nums">{kb.doc_count}</div>
                <div className="text-muted-foreground mt-0.5 text-xs">文档</div>
              </div>
              <div className="text-right">
                <div className="font-mono text-xl leading-none tabular-nums">
                  {kb.chunk_count.toLocaleString()}
                </div>
                <div className="text-muted-foreground mt-0.5 text-xs">chunks</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除知识库「{kb.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。库下的 {kb.doc_count} 篇文档与{' '}
              {kb.chunk_count.toLocaleString()} 条向量将一并清除。
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
              variant="destructive"
            >
              {deleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
