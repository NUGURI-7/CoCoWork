import { useEffect, useState } from 'react'
import { ring } from 'ldrs'

import { listAgents } from '@/api/agent'
import { AgentAvatar } from '@/components/brand/AgentAvatar'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { Agent } from '@/types'

ring.register()

interface RecruitDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 招募该 agent —— 父级调 API + refetch；resolve 后弹窗自关，reject 则保留弹窗。 */
  onRecruit: (agentId: string) => Promise<void>
  /** 已招募的 agent id —— 列表中置灰防重复招募（后端 unique 409 兜底）。 */
  recruitedAgentIds: string[]
}

type SourceTab = 'template' | 'agent'

/**
 * 招募成员弹窗（spec §5.2）
 *
 * 两种来源：
 * - 从我的 Agent：招你已建好的 Agent（自带 prompt/资源），引用入空间。
 * - 从模板：拿基础模板招「毛坯」——「无 agent 行」的临时成员，后端尚未支持，暂禁用。
 */
export function RecruitDialog({
  open,
  onOpenChange,
  onRecruit,
  recruitedAgentIds,
}: RecruitDialogProps) {
  const [tab, setTab] = useState<SourceTab>('agent')
  const [agents, setAgents] = useState<Agent[]>([])
  const [loadingAgents, setLoadingAgents] = useState(false)
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // 开弹窗：复位选择 + 拉自己的 Agent 列表
  useEffect(() => {
    if (!open) return
    setTab('agent')
    setSelectedAgentId(null)

    let cancelled = false
    setLoadingAgents(true)
    listAgents()
      .then((list) => {
        if (!cancelled) setAgents(list)
      })
      .catch(() => {
        // 拦截器已 toast
      })
      .finally(() => {
        if (!cancelled) setLoadingAgents(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const recruited = new Set(recruitedAgentIds)
  const canRecruit = !!selectedAgentId && !submitting

  async function handleSubmit() {
    if (!selectedAgentId) return
    setSubmitting(true)
    try {
      await onRecruit(selectedAgentId)
      onOpenChange(false)
    } catch {
      // 失败保留弹窗（拦截器已 toast），用户可重试 / 换选
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>招募成员</DialogTitle>
          <DialogDescription>
            招你已建好的 Agent 进入工作空间（自带 prompt / 资源）
          </DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={(v) => setTab(v as SourceTab)}>
          <TabsList>
            <TabsTrigger value="agent">从我的 Agent</TabsTrigger>
            <TabsTrigger value="template" disabled>
              从模板（敬请期待）
            </TabsTrigger>
          </TabsList>

          <TabsContent value="agent" className="mt-3">
            {loadingAgents ? (
              <div className="flex h-40 items-center justify-center">
                <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
              </div>
            ) : agents.length === 0 ? (
              <p className="text-muted-foreground py-8 text-center text-sm">
                你还没创建 Agent
              </p>
            ) : (
              <div className="grid max-h-72 grid-cols-2 gap-2 overflow-y-auto">
                {agents.map((a) => {
                  const isRecruited = recruited.has(a.id)
                  const sel = selectedAgentId === a.id
                  return (
                    <button
                      key={a.id}
                      type="button"
                      disabled={isRecruited}
                      onClick={() => setSelectedAgentId(a.id)}
                      className={cn(
                        'flex items-center gap-3 rounded-lg border p-3 text-left transition',
                        isRecruited
                          ? 'cursor-not-allowed opacity-50'
                          : sel
                            ? 'border-brand bg-brand-subtle'
                            : 'hover:bg-muted',
                      )}
                    >
                      <AgentAvatar seed={a.id} src={a.config?.ui?.avatar_url} alt={a.name} />
                      <div className="min-w-0 flex-1">
                        <div
                          className={cn(
                            'truncate text-sm font-medium',
                            sel && !isRecruited && 'text-brand',
                          )}
                        >
                          {a.name}
                        </div>
                        <div className="text-muted-foreground truncate text-xs">
                          {isRecruited ? '已在空间中' : a.description || '暂无描述'}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </TabsContent>

          <TabsContent value="template" className="mt-3">
            <p className="text-muted-foreground py-8 text-center text-sm">
              从模板招募即将开放
            </p>
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canRecruit} onClick={handleSubmit}>
            {submitting ? '招募中...' : '招募'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
