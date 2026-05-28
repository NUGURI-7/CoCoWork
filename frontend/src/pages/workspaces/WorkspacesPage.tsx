import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Layers, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { Workspace } from '@/types'
import { CreateWorkspaceDialog } from './CreateWorkspaceDialog'
import { WorkspaceCard } from './WorkspaceCard'
import { useWorkspaceMockStore } from './workspace-mock-store'

/** /workspaces — 工作空间列表页（Header + 卡片网格） */
export default function WorkspacesPage() {
  const navigate = useNavigate()
  const workspaces = useWorkspaceMockStore((s) => s.workspaces)
  const addWorkspace = useWorkspaceMockStore((s) => s.add)
  const removeWorkspace = useWorkspaceMockStore((s) => s.remove)
  const [dialogOpen, setDialogOpen] = useState(false)

  function handleCreate(ws: Workspace) {
    addWorkspace(ws)
    toast.success(`工作空间「${ws.name}」已创建`)
    navigate({ to: '/workspaces/$workspaceId', params: { workspaceId: ws.id } })
  }

  function handleDelete(id: string) {
    removeWorkspace(id)
    useWorkspaceTabsStore.getState().close(`/workspaces/${id}`)
  }

  return (
    <div className="min-w-0 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">工作空间</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            把 agent 招进同一会话协作 —— 管家调度 + @ 直选，资源共享注入。
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
      {workspaces.length === 0 ? (
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
