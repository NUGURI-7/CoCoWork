import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ChevronLeft, PanelLeft, PanelRight } from 'lucide-react'
import { toast } from 'sonner'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Conversation, WorkspaceMember } from '@/types'

import { ArtifactPanel } from './ArtifactPanel'
import { ConversationSwitcher } from './ConversationSwitcher'
import { MemberRoster } from './MemberRoster'
import { RecruitDialog } from './RecruitDialog'
import { WorkspaceChat } from './WorkspaceChat'
import { useWorkspaceMockStore } from './workspace-mock-store'

/**
 * /workspaces/$workspaceId — 工作空间详情页
 *
 * 三栏：通讯录（左 240）/ 主对话（中，flex-1）/ 产出物面板（右 320，可关）
 * 关闭产出物后，顶部面包屑行右侧出「产出物」按钮重新打开。
 */
export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams({ from: '/_authenticated/workspaces/$workspaceId' })
  const workspace = useWorkspaceMockStore((s) => s.getById(workspaceId))
  const updateWorkspace = useWorkspaceMockStore((s) => s.update)
  const addConversation = useWorkspaceMockStore((s) => s.addConversation)
  const [recruitOpen, setRecruitOpen] = useState(false)
  const [rosterOpen, setRosterOpen] = useState(true)
  const [artifactOpen, setArtifactOpen] = useState(true)
  // 初始化选中第一个 conversation（按 mock 顺序）。后续切换 / 新建会改写。
  const [currentConvId, setCurrentConvId] = useState<string | null>(
    workspace?.conversations[0]?.id ?? null,
  )

  useTabTitle(`/workspaces/${workspaceId}`, workspace?.name)

  if (!workspace) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-center">
        <p className="text-foreground text-sm font-medium">工作空间不存在</p>
        <p className="text-muted-foreground text-xs">
          可能已被删除，或刷新后丢失（v0 mock 是内存存储）
        </p>
        <Link
          to="/workspaces"
          className="text-brand mt-2 inline-flex items-center gap-1 text-sm hover:underline"
        >
          <ChevronLeft className="size-3.5" />
          返回工作空间
        </Link>
      </div>
    )
  }

  function handleRecruit(member: WorkspaceMember) {
    // 从 store 实时取最新 workspace，避免闭包抓老 members
    const cur = useWorkspaceMockStore.getState().getById(workspaceId)
    if (!cur) return
    updateWorkspace(workspaceId, { members: [...cur.members, member] })
    toast.success(`成员「${member.name}」已加入`)
  }

  function handleNewConversation() {
    const now = new Date().toISOString()
    const newConv: Conversation = {
      id: crypto.randomUUID(),
      title: '新对话',
      created_at: now,
      updated_at: now,
    }
    addConversation(workspaceId, newConv)
    setCurrentConvId(newConv.id)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      {/* 顶部：面包屑 + 右侧产出物 toggle（关闭时显示） */}
      <div className="flex items-center justify-between gap-3">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/workspaces" className="inline-flex items-center gap-1">
                  <ChevronLeft className="size-3.5" />
                  工作空间
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{workspace.name}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="flex items-center gap-1">
          {!rosterOpen && (
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setRosterOpen(true)}
            >
              <PanelLeft className="size-4" />
              成员
            </Button>
          )}
          {!artifactOpen && (
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setArtifactOpen(true)}
            >
              <PanelRight className="size-4" />
              产出物
            </Button>
          )}
        </div>
      </div>

      {/* 三栏 */}
      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
        {rosterOpen && (
          <div className="w-60 shrink-0">
            <MemberRoster
              members={workspace.members}
              onRecruit={() => setRecruitOpen(true)}
              onClose={() => setRosterOpen(false)}
            />
          </div>
        )}
        <div className="bg-background flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-lg border shadow-sm">
          <ConversationSwitcher
            conversations={workspace.conversations}
            currentId={currentConvId}
            onSelect={setCurrentConvId}
            onNew={handleNewConversation}
          />
          <WorkspaceChat
            key={currentConvId ?? 'none'}
            members={workspace.members}
          />
        </div>
        {artifactOpen && (
          <div className="w-80 shrink-0">
            <ArtifactPanel onClose={() => setArtifactOpen(false)} />
          </div>
        )}
      </div>

      <RecruitDialog
        open={recruitOpen}
        onOpenChange={setRecruitOpen}
        onRecruit={handleRecruit}
      />
    </div>
  )
}
