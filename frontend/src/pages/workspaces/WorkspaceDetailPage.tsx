import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ring } from 'ldrs'
import { ChevronLeft, PanelLeft, PanelRight, Settings2 } from 'lucide-react'
import { toast } from 'sonner'

import { createConversation, getWorkspace, listConversations } from '@/api/workspace'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Conversation, Workspace } from '@/types'
import { supervisor, type WorkspaceMember } from './mock'

import { ArtifactPanel } from './ArtifactPanel'
import { ConversationSwitcher } from './ConversationSwitcher'
import { MemberRoster } from './MemberRoster'
import { RecruitDialog } from './RecruitDialog'
import { WorkspaceChat } from './WorkspaceChat'
import { WorkspaceSettingsPanel } from './WorkspaceSettingsPanel'

/** 右栏当前显示的面：配置 / 产出物 / 收起 */
type RightPanelFace = 'config' | 'artifact' | null

/**
 * 右栏 3D 翻转容器 —— 配置 / 产出物共用一块地，rotateY 翻面切换。
 * 两面常驻 DOM（backface-hidden 各藏一半），翻转纯 CSS 零重挂。
 */
function FlipPanel({
  face,
  front,
  back,
}: {
  face: 'front' | 'back'
  front: ReactNode
  back: ReactNode
}) {
  return (
    <div className="h-full [perspective:1200px]">
      <div
        className={cn(
          'relative h-full transition-transform duration-500 [transform-style:preserve-3d]',
          face === 'back' && '[transform:rotateY(180deg)]',
        )}
      >
        <div className="absolute inset-0 [backface-visibility:hidden]">{front}</div>
        <div className="absolute inset-0 [transform:rotateY(180deg)] [backface-visibility:hidden]">
          {back}
        </div>
      </div>
    </div>
  )
}

ring.register()

/**
 * /workspaces/$workspaceId — 工作空间详情页
 *
 * 三栏：通讯录（左 240）/ 主对话（中，flex-1）/ 产出物面板（右 320，可关）
 * 关闭产出物后，顶部面包屑行右侧出「产出物」按钮重新打开。
 *
 * 接真状态：workspace 本体 + conversation 列表/创建 走真接口；
 * 通讯录成员是本地 mock（后端 member 接口 d-2 招募片接真）。
 */
export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams({ from: '/_authenticated/workspaces/$workspaceId' })
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConvId, setCurrentConvId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [recruitOpen, setRecruitOpen] = useState(false)
  const [rosterOpen, setRosterOpen] = useState(true)
  // 右栏默认展示配置面（新空间第一件事是配管家）
  const [rightPanel, setRightPanel] = useState<RightPanelFace>('config')
  // 成员本地 mock：固定一个管家；招募 push 本地纯 UI（d-2 接真替换）
  const [members, setMembers] = useState<WorkspaceMember[]>(() => [supervisor()])

  useTabTitle(`/workspaces/${workspaceId}`, workspace?.name)

  // 管家是否已配 chat 模型 —— 决定对话区可不可发（保存配置后 setWorkspace 自动翻转）
  const supervisorReady = useMemo(() => {
    const sup = workspace?.supervisor as
      | { models?: { chat?: { id?: string } } }
      | undefined
    return Boolean(sup?.models?.chat?.id)
  }, [workspace])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setNotFound(false)
      try {
        const [ws, convs] = await Promise.all([
          getWorkspace(workspaceId),
          listConversations(workspaceId),
        ])
        if (cancelled) return
        setWorkspace(ws)
        if (convs.length > 0) {
          // 后端按 updated_at 倒序，第一条 = 最近活跃
          setConversations(convs)
          setCurrentConvId(convs[0].id)
        } else {
          // 新空间无对话：自动建一条，保证「进来就能打字」
          const created = await createConversation(workspaceId)
          if (cancelled) return
          setConversations([created])
          setCurrentConvId(created.id)
        }
      } catch {
        // 404 / 网络失败统一进 not-found 空态（拦截器已 toast 具体原因）
        if (!cancelled) setNotFound(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [workspaceId])

  async function handleNewConversation() {
    try {
      const created = await createConversation(workspaceId)
      setConversations((prev) => [created, ...prev])
      setCurrentConvId(created.id)
    } catch {
      // 拦截器已 toast
    }
  }

  function handleRecruit(member: WorkspaceMember) {
    // d-2 接真前的本地 mock：纯 UI push，刷新即丢
    setMembers((prev) => [...prev, member])
    toast.success(`成员「${member.name}」已加入`)
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  if (notFound || !workspace) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-center">
        <p className="text-foreground text-sm font-medium">工作空间不存在</p>
        <p className="text-muted-foreground text-xs">可能已被删除</p>
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
          {/* 右栏两面常驻开关：点当前面 = 收起，点另一面 = 翻转 */}
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              rightPanel === 'config'
                ? 'text-brand bg-brand-subtle hover:text-brand'
                : 'text-muted-foreground hover:text-foreground',
            )}
            onClick={() => setRightPanel((p) => (p === 'config' ? null : 'config'))}
          >
            <Settings2 className="size-4" />
            配置
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              rightPanel === 'artifact'
                ? 'text-brand bg-brand-subtle hover:text-brand'
                : 'text-muted-foreground hover:text-foreground',
            )}
            onClick={() => setRightPanel((p) => (p === 'artifact' ? null : 'artifact'))}
          >
            <PanelRight className="size-4" />
            产出物
          </Button>
        </div>
      </div>

      {/* 三栏 */}
      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
        {rosterOpen && (
          <div className="w-60 shrink-0">
            <MemberRoster
              members={members}
              onRecruit={() => setRecruitOpen(true)}
              onClose={() => setRosterOpen(false)}
            />
          </div>
        )}
        <div className="bg-background flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-lg border shadow-sm">
          <ConversationSwitcher
            conversations={conversations}
            currentId={currentConvId}
            onSelect={setCurrentConvId}
            onNew={handleNewConversation}
          />
          {currentConvId ? (
            <WorkspaceChat
              key={currentConvId}
              workspaceId={workspaceId}
              conversationId={currentConvId}
              supervisorReady={supervisorReady}
            />
          ) : (
            <div className="text-muted-foreground/70 flex flex-1 items-center justify-center text-sm">
              选择或新建一个对话
            </div>
          )}
        </div>
        {rightPanel !== null && (
          <div className="w-80 shrink-0">
            <FlipPanel
              face={rightPanel === 'config' ? 'front' : 'back'}
              front={
                <WorkspaceSettingsPanel
                  workspace={workspace}
                  onSaved={setWorkspace}
                  onClose={() => setRightPanel(null)}
                />
              }
              back={<ArtifactPanel onClose={() => setRightPanel(null)} />}
            />
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
