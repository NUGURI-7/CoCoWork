import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { Link, Outlet, useMatches, useNavigate, useParams } from '@tanstack/react-router'
import { ring } from 'ldrs'
import {
  ChevronLeft,
  Expand,
  MessagesSquare,
  Minimize2,
  PanelLeft,
  PanelRight,
  Settings2,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  createConversation,
  deleteConversation,
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
import { SidebarTrigger, useSidebar } from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'
import { disposeAllChatStores, disposeChatStore } from '@/stores/chat-registry'
import { useImmersiveStore } from '@/stores/immersive'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Conversation, Workspace, WorkspaceMemberOut } from '@/types'
import { SUPERVISOR_ROSTER, memberToRoster, type RosterMember } from './roster'

import { ArtifactPanel } from './ArtifactPanel'
import { ConversationPanel } from './ConversationPanel'
import { ConversationSwitcher } from './ConversationSwitcher'
import { MemberRoster, MemberStrip } from './MemberRoster'
import { RecruitDialog } from './RecruitDialog'
import { WorkspaceSettingsPanel } from './WorkspaceSettingsPanel'
import { WorkspaceShellContext } from './shell-context'

/** 右栏当前显示的面：配置 / 产出物 / 收起 */
type RightPanelFace = 'config' | 'artifact' | null

/**
 * 右栏切换容器 —— 配置 / 产出物共用一块地，淡入淡出切面。
 * 两面常驻 DOM（叠放，非当前面 opacity-0 + pointer-events-none），切换纯 CSS 零重挂。
 *
 * 用 2D 淡切而非 3D 翻转：3D（perspective + preserve-3d + backface-hidden）的合成上下文
 * 会让面内 overflow 滚动容器在 Chrome 里命中失效（程序化能滚、滚轮/拖拽不动），
 * 故弃 3D，换零副作用的 opacity 过渡。
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
    <div className="relative h-full">
      <div
        className={cn(
          'absolute inset-0 transition-opacity duration-300',
          face === 'front' ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      >
        {front}
      </div>
      <div
        className={cn(
          'absolute inset-0 transition-opacity duration-300',
          face === 'back' ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      >
        {back}
      </div>
    </div>
  )
}

ring.register()

/**
 * /workspaces/$workspaceId — 工作空间详情页
 *
 * 三栏：左（非沉浸 = 成员 roster，可关；沉浸 = 会话面板，可整块开关）/ 主对话
 * （中，flex-1）/ 配置·产物面板（右 320，可关，翻转）。
 *
 * 沉浸模式（每空间记忆）：藏掉顶栏 / TabBar / 面包屑 / 右侧面板 + 强制收起全局侧栏，
 * 会话铺满；成员降级为沉浸顶栏右侧的头像条（不再单占一行）；会话面板为对话区左侧
 * 的浮层（绝对定位，不挤压 message list），开关在沉浸顶栏。退出按钮在沉浸顶栏行尾。
 *
 * 接真状态：workspace 本体 + conversation 列表/创建 + 成员招募/列表/踢人 全走真接口；
 * 管家是合成行（workspace.supervisor，非 members 表的行），固定置顶。
 */
export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams({ from: '/_authenticated/workspaces/$workspaceId' })
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const navigate = useNavigate()
  // 当前会话 id —— 真源在 URL（子路由 /c/$conversationId 的 path 参数），从匹配树里读
  const matches = useMatches()
  const currentConvId = useMemo<string | null>(() => {
    for (const m of matches) {
      const p = m.params as { conversationId?: string }
      if (p?.conversationId) return p.conversationId
    }
    return null
  }, [matches])
  // 切会话 = 改 URL（push，前进后退能在会话间跳）；id=null 回 index；程序化跳转传 replace
  const setCurrentConvId = useCallback(
    (id: string | null, opts?: { replace?: boolean }) => {
      if (id == null) {
        navigate({
          to: '/workspaces/$workspaceId',
          params: { workspaceId },
          replace: opts?.replace,
        })
      } else {
        navigate({
          to: '/workspaces/$workspaceId/c/$conversationId',
          params: { workspaceId, conversationId: id },
          replace: opts?.replace,
        })
      }
    },
    [navigate, workspaceId],
  )
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [recruitOpen, setRecruitOpen] = useState(false)
  // 沉浸模式下「产物」右栏开关 —— 用真侧栏（非 Sheet）：无遮罩，产物可拖进对话框
  const [immersiveArtifactOpen, setImmersiveArtifactOpen] = useState(false)
  // 非沉浸模式宽 roster 的开关（沉浸模式走左栏常驻面板，与此无关）
  const [rosterOpen, setRosterOpen] = useState(true)
  // 沉浸左栏会话面板开/关 —— 每空间记忆（刷新还原），默认展开
  const conversationsOpen = useImmersiveStore((s) => s.convOpen[workspaceId] ?? true)
  const setConvOpen = useImmersiveStore((s) => s.setConvOpen)
  // 全局侧栏开关 —— 沉浸模式强制收起、退出复原。shadcn 的 setOpen 依赖 open，每次
  // 开合都换引用；用 ref 持最新、effect 只认 immersive，避免用户手动展开后被 effect
  // 重跑又关掉（那会让全局栏 trigger 看着「失效」）。
  const { setOpen: setGlobalSidebarOpen } = useSidebar()
  const setGlobalSidebarOpenRef = useRef(setGlobalSidebarOpen)
  setGlobalSidebarOpenRef.current = setGlobalSidebarOpen
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

  // 沉浸模式：进入即收起全局侧栏，退出 / 离开页面复原。放 effect（而非 enter()）→
  // 刷新进「上次沉浸」的空间也会重跑，始终默认收起；非沉浸不触发（body 早返回），
  // 不干扰用户在普通模式下自己折叠全局栏的偏好。
  useEffect(() => {
    if (!immersive) return
    setGlobalSidebarOpenRef.current(false)
    return () => setGlobalSidebarOpenRef.current(true)
  }, [immersive])

  // 离开本空间 / 切到别的空间 → 清空 chat-registry，回收所有对话桶（含中断在跑的
  // 流）。桶只在「逛当前空间」期间常驻，给内存封顶。
  useEffect(() => {
    return () => disposeAllChatStores()
  }, [workspaceId])

  useTabTitle(`/workspaces/${workspaceId}`, workspace?.name)

  // 管家是否已配 chat 模型 —— 决定对话区可不可发（保存配置后 setWorkspace 自动翻转）
  const supervisorReady = useMemo(() => {
    const sup = workspace?.supervisor as { models?: { chat?: { id?: string } } } | undefined
    return Boolean(sup?.models?.chat?.id)
  }, [workspace])

  // 通讯录 = 合成管家置顶 + 招募成员；recruitedAgentIds 给招募弹窗置灰防重招
  const roster = useMemo<RosterMember[]>(
    () => [SUPERVISOR_ROSTER, ...members.map(memberToRoster)],
    [members],
  )
  const recruitedAgentIds = useMemo(() => members.map((m) => m.agent.id), [members])

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
          // 后端按 updated_at 倒序，第一条 = 最近活跃；选中哪条交给下方 URL 同步 effect
          setConversations(convs)
        } else {
          // 新空间无对话：自动建一条，保证「进来就能打字」
          const created = await createConversation(workspaceId)
          if (cancelled) return
          setConversations([created])
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

  // URL 同步：会话加载完后，若当前 URL 没指向有效会话（落在 index 或 cid 失效/跨空间残留），
  // replace 跳到最近一条。自动建会话由 load 负责，这里只管把 URL 钉到某一条。
  useEffect(() => {
    if (loading || conversations.length === 0) return
    const valid = conversations.some((c) => c.id === currentConvId)
    if (!valid) setCurrentConvId(conversations[0].id, { replace: true })
  }, [loading, conversations, currentConvId, setCurrentConvId])

  async function handleNewConversation() {
    try {
      const created = await createConversation(workspaceId)
      setConversations((prev) => [created, ...prev])
      setCurrentConvId(created.id)
    } catch {
      // 拦截器已 toast
    }
  }

  async function handleDeleteConversation(id: string) {
    try {
      await deleteConversation(workspaceId, id)
    } catch {
      // 拦截器已 toast；删除失败不动本地状态
      return
    }
    // 回收该对话的桶（中断在跑的流 + 释放内存）
    disposeChatStore(id)

    const remaining = conversations.filter((c) => c.id !== id)
    const deletingCurrent = id === currentConvId

    // 删的不是当前对话、或还有剩：更新列表，必要时把当前切到最近一条
    if (!deletingCurrent || remaining.length > 0) {
      setConversations(remaining)
      if (deletingCurrent) {
        const next = [...remaining].sort(
          (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
        )[0]
        setCurrentConvId(next.id, { replace: true })
      }
      return
    }

    // 删的是当前且一条不剩：自动新建一条，保「进来就能打字」不变式
    try {
      const created = await createConversation(workspaceId)
      setConversations([created])
      setCurrentConvId(created.id, { replace: true })
    } catch {
      setConversations([])
      setCurrentConvId(null, { replace: true })
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
    <WorkspaceShellContext.Provider value={{ supervisorReady }}>
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

        {/* 沉浸模式：极简全宽顶栏 —— 收起全局侧栏 + 当前对话标题 + 产物/退出。
          内容行整体落其下，左栏卡片不再顶到内容区最上沿。 */}
        {immersive && (
          <ConversationSwitcher
            conversations={conversations}
            currentId={currentConvId}
            onSelect={setCurrentConvId}
            onNew={handleNewConversation}
            onDelete={handleDeleteConversation}
            immersive
            actions={<MemberStrip members={roster} onRecruit={() => setRecruitOpen(true)} />}
            leading={
              <>
                <SidebarTrigger className="text-muted-foreground hover:text-foreground -ml-0.5" />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setConvOpen(workspaceId, !conversationsOpen)}
                  title={conversationsOpen ? '收起会话' : '展开会话'}
                  className={cn(
                    'size-7',
                    conversationsOpen
                      ? 'text-brand bg-brand-subtle hover:text-brand'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  <MessagesSquare className="size-4" />
                </Button>
              </>
            }
            trailing={
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setImmersiveArtifactOpen((v) => !v)}
                  title="产物"
                  className={cn(
                    'size-7',
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
                  className="text-muted-foreground hover:text-foreground size-7"
                >
                  <Minimize2 className="size-4" />
                </Button>
              </>
            }
          />
        )}

        {/* 内容行 —— 沉浸：左栏双卡 + 对话区（无内层 switcher）；非沉浸：宽 roster + 右侧配置/产物 */}
        <div className={cn('flex min-h-0 flex-1 overflow-hidden', immersive ? 'gap-3' : 'gap-4')}>
          {/* 非沉浸：成员 roster 占左栏 flex 位。沉浸下会话面板改走浮层（见下方对话区内） */}
          {!immersive && rosterOpen && (
            <div className="w-60 shrink-0">
              <MemberRoster
                members={roster}
                onRecruit={() => setRecruitOpen(true)}
                onRemove={handleRemove}
                onClose={() => setRosterOpen(false)}
              />
            </div>
          )}
          <div
            className={cn(
              'relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden',
              !immersive && 'bg-background rounded-lg border shadow-sm',
            )}
          >
            {/* 沉浸：会话面板浮在对话区左侧（绝对定位，不占布局宽度 → 不挤压 message
              list），带阴影像浮卡；开关仍在沉浸顶栏，开/关每空间记忆 */}
            {immersive && conversationsOpen && (
              <div className="absolute top-2 bottom-2 left-2 z-20 w-60 rounded-lg shadow-xl">
                <ConversationPanel
                  conversations={conversations}
                  currentId={currentConvId}
                  onSelect={setCurrentConvId}
                  onNew={handleNewConversation}
                  onDelete={handleDeleteConversation}
                />
              </div>
            )}
            {/* 沉浸模式下标题/退出都已上移到全宽顶栏，对话区内不再重复 switcher */}
            {!immersive && (
              <ConversationSwitcher
                conversations={conversations}
                currentId={currentConvId}
                onSelect={setCurrentConvId}
                onNew={handleNewConversation}
                onDelete={handleDeleteConversation}
              />
            )}
            {/* 对话区 = 子路由 /c/$conversationId；无会话时 index 路由占位、外壳 effect 跳最近一条 */}
            <Outlet />
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
    </WorkspaceShellContext.Provider>
  )
}
