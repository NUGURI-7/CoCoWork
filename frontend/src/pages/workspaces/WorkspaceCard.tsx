import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import dayjs from 'dayjs'
import { Crown, MoreHorizontal, Trash2 } from 'lucide-react'

import { AgentAvatar, SUPERVISOR_SEED } from '@/components/brand/AgentAvatar'

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
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import type { Workspace } from '@/types'

interface WorkspaceCardProps {
  workspace: Workspace
  onDelete?: (id: string) => void
}

/** 管家头像（d-1 后端只有 supervisor；d-2 member 接真后恢复成员头像堆叠 + N 计数） */
function SupervisorBadge() {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <AgentAvatar seed={SUPERVISOR_SEED} alt="管家" className="bg-background size-7" />
      <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
        <Crown className="text-brand size-3.5" />
        管家
      </span>
    </div>
  )
}

export function WorkspaceCard({ workspace, onDelete }: WorkspaceCardProps) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)

  function handleClick() {
    navigate({ to: '/workspaces/$workspaceId', params: { workspaceId: workspace.id } })
  }

  function handleDelete() {
    // 成功/失败的 toast 归父级（它才知道 API 结果）
    onDelete?.(workspace.id)
    setConfirmOpen(false)
  }

  return (
    <>
      <Card className="card-interactive min-w-0 gap-0 py-0" onClick={handleClick}>
        <CardContent className="flex flex-col gap-4 p-5">
          {/* 标题区 */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate font-medium">{workspace.name}</h3>
              <p
                className={cn(
                  'text-muted-foreground mt-0.5 line-clamp-1 text-sm',
                  !workspace.description && 'italic',
                )}
              >
                {workspace.description || '暂无描述'}
              </p>
            </div>
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-foreground -mr-1 size-6"
                  >
                    <MoreHorizontal className="size-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
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
          </div>

          <Separator />

          {/* 数据区：管家标识 | 更新时间 */}
          <div className="flex items-center justify-between gap-3">
            <SupervisorBadge />
            <span className="text-muted-foreground shrink-0 text-xs">
              {dayjs(workspace.updated_at).fromNow()}
            </span>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除工作空间「{workspace.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。空间内的成员实例、对话与产出物将一并清除（招募来源的模板 / Agent 不受影响）。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              variant="destructive"
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
