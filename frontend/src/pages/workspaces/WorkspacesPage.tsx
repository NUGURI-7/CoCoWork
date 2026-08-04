import { useEffect, useState } from 'react'
import { ring } from 'ldrs'
import { Layers, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { deleteWorkspace } from '@/api/workspace'
import { Button } from '@/components/ui/button'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import { useWorkspaceSession } from '@/stores/workspace-session'
import type { Workspace } from '@/types'
import { CreateWorkspaceDialog } from './CreateWorkspaceDialog'
import { WorkspaceCard } from './WorkspaceCard'

ring.register()

/** /workspaces — 工作空间列表页（Header + 卡片网格） */
export default function WorkspacesPage() {
  // 列表真源在 workspace-session store（与侧栏空间选择器同步）
  const workspaces = useWorkspaceSession((s) => s.workspaces)
  const workspacesLoaded = useWorkspaceSession((s) => s.workspacesLoaded)
  const loadWorkspaces = useWorkspaceSession((s) => s.loadWorkspaces)
  const addWorkspace = useWorkspaceSession((s) => s.addWorkspace)
  const removeWorkspace = useWorkspaceSession((s) => s.removeWorkspace)
  const [loading, setLoading] = useState(!workspacesLoaded)
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    // 进列表页刷新一次最新（反映他处的增删）；store 写回后侧栏选择器同步更新
    setLoading(true)
    loadWorkspaces().finally(() => setLoading(false))
  }, [loadWorkspaces])

  function handleCreate(ws: Workspace) {
    // 创建接口返完整 WorkspaceOut，头插 store（列表按活跃倒序）不重拉。
    addWorkspace(ws)
    toast.success(`工作空间「${ws.name}」已创建`)
  }

  async function handleDelete(id: string) {
    const target = workspaces.find((w) => w.id === id)
    try {
      await deleteWorkspace(id)
      removeWorkspace(id)
      useWorkspaceTabsStore.getState().close(`/workspaces/${id}`)
      toast.success(`工作空间「${target?.name ?? ''}」已删除`)
    } catch {
      // 全局拦截器已 toast 失败原因；列表保持原样
    }
  }

  return (
    <div className="min-w-0 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">工作空间</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            把 agent 招进同一会话协作 —— Supervisor 调度 + @ 直选，资源共享注入。
          </p>
        </div>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="size-4" />
          创建工作空间
        </Button>
      </div>

      <CreateWorkspaceDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreate={handleCreate}
      />

      {/* 卡片网格 */}
      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
        </div>
      ) : workspaces.length === 0 ? (
        <EmptyState onCreate={() => setDialogOpen(true)} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {workspaces.map((ws) => (
            <WorkspaceCard key={ws.id} workspace={ws} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="text-muted-foreground flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-16 text-center">
      <Layers className="size-8" />
      <div className="space-y-1">
        <div className="text-foreground text-sm font-medium">你还没有工作空间</div>
        <div className="text-xs">创建一个，把 agent 招进来协作</div>
      </div>
      <Button size="sm" variant="outline" onClick={onCreate}>
        <Plus className="size-4" />
        创建工作空间
      </Button>
    </div>
  )
}
