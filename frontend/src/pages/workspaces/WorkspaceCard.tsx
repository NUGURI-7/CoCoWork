import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { MoreHorizontal, Trash2, Users } from 'lucide-react'
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

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${Math.max(minutes, 1)} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

/** 成员头像堆叠（最多显示 4 个，多余折成 +N） */
function MemberStack({ workspace }: { workspace: Workspace }) {
  const shown = workspace.members.slice(0, 4)
  const rest = workspace.members.length - shown.length
  return (
    <div className="flex items-center -space-x-2">
      {shown.map((m) => (
        <img
          key={m.id}
          src={m.avatar_url ?? '/gopher-fcb-glass.png'}
          alt={m.name}
          title={m.name}
          className="bg-background ring-background size-7 rounded-full object-cover ring-2"
        />
      ))}
      {rest > 0 && (
        <div className="bg-muted text-muted-foreground ring-background flex size-7 items-center justify-center rounded-full text-[11px] font-medium ring-2">
          +{rest}
        </div>
      )}
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
    onDelete?.(workspace.id)
    toast.success(`工作空间「${workspace.name}」已删除`)
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

          {/* 数据区：成员头像堆叠 + 成员数 | 更新时间 */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <MemberStack workspace={workspace} />
              <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                <Users className="size-3.5" />
                {workspace.members.length} 成员
              </span>
            </div>
            <span className="text-muted-foreground shrink-0 text-xs">
              {timeAgo(workspace.updated_at)}
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
