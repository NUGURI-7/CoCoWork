import { useState } from 'react'
import { CircleCheck, CircleX, MoreHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { deleteModel } from '@/api/model'
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
import { Card, CardContent } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { AIModel } from '@/types'

/** 模型类型 → 标签 */
const modelTypeLabel: Record<string, string> = {
  chat: '对话',
  embedding: '向量',
  rerank: '重排序',
}

/** 模型类型 → 颜色 */
const modelTypeBadgeVariant: Record<string, string> = {
  chat: 'bg-blue-50 text-blue-700 border-blue-200',
  embedding: 'bg-amber-50 text-amber-700 border-amber-200',
  rerank: 'bg-violet-50 text-violet-700 border-violet-200',
}

interface AIModelCardProps {
  model: AIModel
  onDeleted?: () => void
}

export function AIModelCard({ model, onDeleted }: AIModelCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteModel(model.id)
      toast.success('模型已删除')
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
      <Card className="min-h-[150px]">
        <CardContent className="flex flex-1 flex-col justify-between gap-2.5">
          <div className="flex items-center justify-between">
            <span
              className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${modelTypeBadgeVariant[model.model_type] ?? ''}`}
            >
              {modelTypeLabel[model.model_type] ?? model.model_type}
            </span>
            {model.is_enabled ? (
              <CircleCheck className="size-3.5 text-success" />
            ) : (
              <CircleX className="text-muted-foreground size-3.5" />
            )}
          </div>
          <div className="flex items-end justify-between gap-2">
            <div className="min-w-0">
              <h4 className="text-base font-medium leading-none">{model.display_name}</h4>
              <p className="text-muted-foreground mt-1 truncate font-mono text-xs">
                {model.model_name}
              </p>
              {model.model_type === 'embedding' && model.meta?.embedding_dim != null && (
                <p className="text-muted-foreground mt-1 text-xs">
                  维度 {model.meta.embedding_dim}
                </p>
              )}
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground -mr-1 size-6 shrink-0 translate-y-3"
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
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除模型「{model.display_name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销，删除后需要重新创建。
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
              className="bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
