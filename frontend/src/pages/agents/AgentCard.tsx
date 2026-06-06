import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Bot, BookOpen, Copy, MoreHorizontal, Trash2, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { deleteAgent } from '@/api/agent'
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
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { Agent } from '@/types'
import { KindBadge } from './KindBadge'
import { mockTemplates } from './mock'

interface AgentCardProps {
  agent: Agent
  /** model id → display_name 反查表（父级 listAllModels 一次性拉好，避免 N+1） */
  modelNameMap?: Map<string, string>
  /** 删除成功后通知父级 refetch */
  onDeleted?: () => void
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

export function AgentCard({ agent, modelNameMap, onDeleted }: AgentCardProps) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // 模板元数据反查（mock 模板池里查 key；找不到回退到 key 本身展示）
  const template = mockTemplates.find((t) => t.key === agent.template)
  const templateName = template?.name ?? agent.template
  const templateKind = template?.kind ?? 'loop'
  const modelId = agent.config.models?.chat?.id
  const modelName = modelId ? modelNameMap?.get(modelId) : null
  const knowledgeCount = agent.config.knowledge?.length ?? 0
  const toolCount =
    (agent.config.tools?.length ?? 0) + (agent.config.skills?.length ?? 0)
  // P0 不暴露上传 UI：所有 Agent 头像统一用默认 gopher；未来加上传后这里 fallback
  const avatarUrl = agent.config.ui?.avatar_url ?? '/gopher-fcb-glass.png'

  function handleClick() {
    navigate({ to: '/agents/$agentId', params: { agentId: agent.id } })
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteAgent(agent.id)
      toast.success(`Agent「${agent.name}」已删除`)
      useWorkspaceTabsStore.getState().close(`/agents/${agent.id}`)
      setConfirmOpen(false)
      onDeleted?.()
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Card className="card-interactive min-w-0 gap-0 py-0" onClick={handleClick}>
        <CardContent className="flex flex-col gap-4 p-5">
          {/* 标题区：头像 + 名字 + 第二行 template · description */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <img
                src={avatarUrl}
                alt={agent.name}
                className="size-10 shrink-0 rounded-full object-cover"
              />
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-medium">{agent.name}</h3>
                <div className="mt-1 flex min-w-0 items-center gap-1.5">
                  <KindBadge kind={templateKind} className="shrink-0" />
                  <p className="text-muted-foreground line-clamp-1 min-w-0 flex-1 text-sm">
                    <span>{templateName}</span>
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
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-foreground -mt-1 -mr-1 size-6"
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

          {/* 数据区：左 meta（模型/知识库/工具） | 右 更新时间 */}
          <div className="flex items-end justify-between gap-3">
            <div className="text-muted-foreground flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
              <span className="inline-flex items-center gap-1">
                <Bot className="size-3.5" />
                {modelId ? (
                  <span className="truncate">{modelName ?? '已选模型'}</span>
                ) : (
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
            <span className="text-muted-foreground shrink-0 text-xs">
              {timeAgo(agent.updated_at)}
            </span>
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
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              className="bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleting ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
