import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ring } from 'ldrs'
import {
  ChevronLeft,
  Expand,
  Minimize2,
  PanelLeft,
  PanelRight,
  Settings2,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  createConversation,
  getWorkspace,
  listConversations,
  listMembers,
  recruitMember,
  removeMember,
} from '@/api/workspace'
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
import { disposeAllChatStores } from '@/stores/chat-registry'
import { useImmersiveStore } from '@/stores/immersive'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Conversation, Workspace, WorkspaceMemberOut } from '@/types'
import { SUPERVISOR_ROSTER, memberToRoster, type RosterMember } from './roster'

import { ArtifactPanel } from './ArtifactPanel'
import { ConversationSwitcher } from './ConversationSwitcher'
import { MemberDock, MemberRoster } from './MemberRoster'
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
 * 三栏：成员（左）/ 主对话（中，flex-1）/ 配置·产物面板（右 320，可关，翻转）。
 * 成员栏两种形态：非沉浸 = 原宽 roster（w-60，可关）；沉浸 = 常驻窄 dock
 * （hover 浮出完整卡）。
 *
 * 沉浸模式（每空间记忆）：藏掉顶栏 / TabBar / 面包屑 / 右侧面板，会话铺满；
 * 成员窄 dock 仍常驻。退出按钮在会话顶部那条 switcher 行尾。
 *
 * 接真状态：workspace 本体 + conversation 列表/创建 + 成员招募/列表/踢人 全走真接口；
 * 管家是合成行（workspace.supervisor，非 members 表的行），固定置顶。
 */
export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams({ from: '/_authenticated/workspaces/$workspaceId' })
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConvId, setCurrentConvId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [recruitOpen, setRecruitOpen] = useState(false)
  // 沉浸模式下「产物」右栏开关 —— 用真侧栏（非 Sheet）：无遮罩，产物可拖进对话框
  const [immersiveArtifactOpen, setImmersiveArtifactOpen] = useState(false)
  // 非沉浸模式宽 roster 的开关（沉浸模式走常驻窄 dock，与此无关）
  const [rosterOpen, setRosterOpen] = useState(true)
  // 右栏默认展示配置面（新空间第一件事是配管家）
  const [rightPanel, setRightPanel] = useState<RightPanelFace>('config')
  // 招募的真成员（后端 MemberOut）；管家是合成行、不在此列
  const [members, setMembers] = useState<WorkspaceMemberOut[]>([])
  // 沉浸模式：藏掉所有 chrome（顶栏 / TabBar / 面包屑 / 左右栏），会话铺满。
  // 每空间各自记忆（prefs 持久化）；active 进页面时同步、离开复位。
  const immersive = useImmersiveStore((s) => s.active)
  const setImmersive = useImmersiveStore((s) => s.set)
  const enterImmersive = useImmersiveStore((s) => s.enter)
  const leaveImmersive = useImmersiveStore((s) => s.leave)

  // 进本空间同步该空间偏好、离开复位。useLayoutEffect 在 paint 前跑 —— 进一个
  // 「上次沉浸」的空间时不会先闪一下 chrome。换 workspaceId 也会重跑。
  useLayoutEffect(() => {
    enterImmersive(workspaceId)
    return () => leaveImmersive()
  }, [workspaceId, enterImmersive, leaveImmersive])

  // 离开本空间 / 切到别的空间 → 清空 chat-registry，回收所有对话桶（含中断在跑的
  // 流）。桶只在「逛当前空间」期间常驻，给内存封顶。
  useEffect(() => {
    return () => disposeAllChatStores()
  }, [workspaceId])

  useTabTitle(`/workspaces/${workspaceId}`, workspace?.name)

  // 管家是否已配 chat 模型 —— 决定对话区可不可发（保存配置后 setWorkspace 自动翻转）
  const supervisorReady = useMemo(() => {
    const sup = workspace?.supervisor as
      | { models?: { chat?: { id?: string } } }
      | undefined
    return Boolean(sup?.models?.chat?.id)
  }, [workspace])

  // 通讯录 = 合成管家置顶 + 招募成员；recruitedAgentIds 给招募弹窗置灰防重招
  const roster = useMemo<RosterMember[]>(
    () => [SUPERVISOR_ROSTER, ...members.map(memberToRoster)],
    [members],
  )
  const recruitedAgentIds = useMemo(
    () => members.map((m) => m.agent.id),
    [members],
  )

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setNotFound(false)
      try {
        const [ws, convs, mems] = await Promise.all([
          getWorkspace(workspaceId),
          listConversations(workspaceId),
          listMembers(workspaceId),
        ])
        if (cancelled) return
        setWorkspace(ws)
        setMembers(mems)
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

  async function handleRecruit(agentId: string) {
    const member = await recruitMember(workspaceId, { agent_id: agentId })
    setMembers((prev) => [...prev, member])
    toast.success(`成员「${member.agent.name}」已加入`)
  }

  async function handleRemove(member: RosterMember) {
    await removeMember(workspaceId, member.id)
    setMembers((prev) => prev.filter((m) => m.id !== member.id))
    toast.success(`成员「${member.name}」已移除`)
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
    <div className={cn('flex min-h-0 flex-1 flex-col', !immersive && 'gap-4')}>
      {/* 顶部：面包屑 + 面板开关 —— 沉浸模式整条隐藏 */}
      {!immersive && (
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
            {/* 沉浸模式：藏掉所有 chrome，会话铺满 */}
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setImmersive(workspaceId, true)}
            >
              <Expand className="size-4" />
              沉浸
            </Button>
          </div>
        </div>
      )}

      {/* 三栏 —— 沉浸用窄 dock（常驻），非沉浸用原宽 roster（可关）+ 右侧配置/产物 */}
      <div className={cn('flex min-h-0 flex-1 overflow-hidden', immersive ? 'gap-3' : 'gap-4')}>
        {immersive ? (
          <MemberDock members={roster} />
        ) : (
          rosterOpen && (
            <div className="w-60 shrink-0">
              <MemberRoster
                members={roster}
                onRecruit={() => setRecruitOpen(true)}
                onRemove={handleRemove}
                onClose={() => setRosterOpen(false)}
              />
            </div>
          )
        )}
        <div
          className={cn(
            'flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden',
            !immersive && 'bg-background rounded-lg border shadow-sm',
          )}
        >
          <ConversationSwitcher
            conversations={conversations}
            currentId={currentConvId}
            onSelect={setCurrentConvId}
            onNew={handleNewConversation}
            trailing={
              // 沉浸模式：行尾放「产物」+ 退出，不与「新对话」打架
              immersive ? (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setImmersiveArtifactOpen((v) => !v)}
                    title="产物"
                    className={cn(
                      'size-8',
                      immersiveArtifactOpen
                        ? 'text-brand bg-brand-subtle hover:text-brand'
                        : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <PanelRight className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setImmersive(workspaceId, false)}
                    title="退出沉浸"
                    className="text-muted-foreground hover:text-foreground size-8"
                  >
                    <Minimize2 className="size-4" />
                  </Button>
                </>
              ) : undefined
            }
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
        {!immersive && rightPanel !== null && (
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
        {/* 沉浸模式产物栏 —— 真侧栏推开会话，无遮罩，产物可拖进对话框。
            不撑满整列：定高 70vh + 垂直居中，跟左侧成员 dock 呼应。 */}
        {immersive && immersiveArtifactOpen && (
          <div className="h-[70vh] max-h-full w-80 shrink-0 self-center">
            <ArtifactPanel onClose={() => setImmersiveArtifactOpen(false)} />
          </div>
        )}
      </div>

      <RecruitDialog
        open={recruitOpen}
        onOpenChange={setRecruitOpen}
        onRecruit={handleRecruit}
        recruitedAgentIds={recruitedAgentIds}
      />
    </div>
  )
}
