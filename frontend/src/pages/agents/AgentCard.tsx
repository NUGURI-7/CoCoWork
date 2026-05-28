import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Bot, BookOpen, Copy, MoreHorizontal, Trash2, Wrench } from 'lucide-react'
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { Agent } from '@/types'

interface AgentCardProps {
  agent: Agent
  /** 不传则 dropdown 删除项 disabled —— v0 列表页接 onDelete 改本地 state */
  onDelete?: (id: string) => void
}

/** 相对时间（简易版） */
function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${Math.max(minutes, 1)} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

export function AgentCard({ agent, onDelete }: AgentCardProps) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)

  function handleClick() {
    navigate({ to: '/agents/$agentId', params: { agentId: agent.id } })
  }

  function handleDelete() {
    onDelete?.(agent.id)
    toast.success(`Agent「${agent.name}」已删除`)
    setConfirmOpen(false)
  }

  const initial = agent.name.slice(0, 1)
  const knowledgeCount = agent.knowledge_ids.length
  const toolCount = agent.tool_ids.length + agent.mcp_ids.length

  return (
    <>
      <Card className="card-interactive min-w-0 gap-0 py-0" onClick={handleClick}>
        <CardContent className="flex flex-col gap-4 p-5">
          {/* 标题区：头像 + 名字 + 第二行 template · description */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <div
                className="flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-medium text-white"
                style={{ backgroundColor: agent.avatar_color }}
              >
                {initial}
              </div>
              <div className="min-w-0">
                <h3 className="truncate font-medium">{agent.name}</h3>
                <p className="text-muted-foreground mt-0.5 line-clamp-1 text-sm">
                  <span>{agent.template_name}</span>
                  {agent.description && (
                    <>
                      <span className="mx-1.5">·</span>
                      <span>{agent.description}</span>
                    </>
                  )}
                </p>
              </div>
            </div>
          </div>

          <Separator />

          {/* 数据区：左 meta（模型/知识库/工具） | 右 更新时间 + 三点 */}
          <div className="flex items-end justify-between gap-3">
            <div className="text-muted-foreground flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
              <span className="inline-flex items-center gap-1">
                <Bot className="size-3.5" />
                {agent.model_display_name ?? (
                  <span className="italic">未选模型</span>
                )}
              </span>
              <span className="inline-flex items-center gap-1">
                <BookOpen className="size-3.5" />
                {knowledgeCount} 知识库
              </span>
              <span className="inline-flex items-center gap-1">
                <Wrench className="size-3.5" />
                {toolCount} 工具
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <span className="text-muted-foreground text-xs">
                {timeAgo(agent.updated_at)}
              </span>
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
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div>
                          <DropdownMenuItem disabled>
                            <Copy className="size-4" />
                            复制为新 Agent
                          </DropdownMenuItem>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="left">v1.5+</TooltipContent>
                    </Tooltip>
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
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除 Agent「{agent.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。Agent 的配置（模型 / prompt / 知识库 / 工具关联）将一并清除。
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
