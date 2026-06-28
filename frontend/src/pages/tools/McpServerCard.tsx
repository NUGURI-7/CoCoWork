import { useState } from 'react'
import { MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { deleteMCPServer, updateMCPServer } from '@/api/mcp'
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
import { Switch } from '@/components/ui/switch'
import type { MCPServer } from '@/types'

import { McpServerAvatar } from './McpServerAvatar'

const transportLabel: Record<string, string> = {
  streamable_http: 'Streamable HTTP',
  sse: 'SSE',
}

/** 卡片展示用：砍掉 query（key 常挂在 ?key=），只留 origin + 路径 */
function displayUrl(url: string): string {
  try {
    const u = new URL(url)
    return u.origin + u.pathname
  } catch {
    return url
  }
}

interface McpServerCardProps {
  server: MCPServer
  /** 点「编辑」时回传整条记录，由父级打开编辑弹窗 */
  onEdit: (server: MCPServer) => void
  /** 删除成功后通知父级 refetch */
  onChanged?: () => void
}

export function McpServerCard({ server, onEdit, onChanged }: McpServerCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [enabled, setEnabled] = useState(server.enabled)
  const [toggling, setToggling] = useState(false)

  async function handleToggle(next: boolean) {
    setEnabled(next) // 乐观更新
    setToggling(true)
    try {
      await updateMCPServer(server.id, { enabled: next })
    } catch {
      setEnabled(!next) // 失败回滚；拦截器已 toast
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteMCPServer(server.id)
      toast.success('MCP server 已删除')
      setConfirmOpen(false)
      onChanged?.()
    } catch {
      // 默认拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Card className="min-h-[150px]">
        <CardContent className="flex flex-1 flex-col gap-3">
          <div className="flex items-start gap-3">
            <McpServerAvatar name={server.name} size={40} />
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-base font-medium leading-none">
                {server.name}
              </h3>
              <p className="text-muted-foreground mt-1 truncate text-xs">
                {displayUrl(server.server_url)}
              </p>
            </div>
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
                  onSelect={(e) => {
                    e.preventDefault()
                    onEdit(server)
                  }}
                >
                  <Pencil className="size-4" />
                  编辑
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

          {server.description && (
            <p className="text-muted-foreground line-clamp-2 text-sm">
              {server.description}
            </p>
          )}

          <div className="mt-auto flex items-center justify-between">
            <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-xs">
              {transportLabel[server.transport] ?? server.transport}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs">
                {enabled ? '已启用' : '已停用'}
              </span>
              <Switch
                checked={enabled}
                onCheckedChange={handleToggle}
                disabled={toggling}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除 MCP server「{server.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。引用了该 server 工具的 Agent 将失去这些工具。
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
