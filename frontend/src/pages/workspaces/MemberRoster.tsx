import { useRef, useState } from 'react'
import { UserPlus, X } from 'lucide-react'

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
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import type { RosterMember } from './roster'

/** 成员运行时状态 —— idle 空闲 / running 运行中 / error 出错 */
type MemberStatus = 'idle' | 'running' | 'error'

const STATUS_DOT: Record<MemberStatus, string> = {
  idle: 'bg-muted-foreground/40',
  running: 'bg-brand animate-pulse',
  error: 'bg-destructive',
}

/**
 * 占位：registry 接真前一律 idle。
 * 真状态要靠「每对话 store 常驻 registry」把后台 thread 是否在跑喂进来，
 * 届时按成员 id 查表，此处再恢复成员入参。
 */
function memberStatus(): MemberStatus {
  return 'idle'
}

// ============ 宽 roster（非沉浸常驻左栏，spec §5.3）============

interface MemberRosterProps {
  /** 已排好序（管家置顶），由页面统一收敛 */
  members: RosterMember[]
  onRecruit: () => void
  /** 踢人（仅 agent 成员可踢；管家无此入口）。 */
  onRemove?: (member: RosterMember) => void | Promise<void>
  /** 传入则在头部显示关闭按钮 */
  onClose?: () => void
}

/**
 * 通讯录（左栏，spec §5.3）
 *
 * 管家固定第一位；其余成员按招募顺序展示。
 * agent 成员行 hover 露出 X → 二次确认后踢人；管家行不可踢。
 */
export function MemberRoster({
  members,
  onRecruit,
  onRemove,
  onClose,
}: MemberRosterProps) {
  // 待确认踢出的成员（null = 关闭确认弹窗）
  const [pendingRemove, setPendingRemove] = useState<RosterMember | null>(null)
  const [removing, setRemoving] = useState(false)

  async function handleConfirmRemove() {
    if (!pendingRemove) return
    setRemoving(true)
    try {
      await onRemove?.(pendingRemove)
      setPendingRemove(null)
    } finally {
      // 失败保留弹窗（拦截器已 toast），用户可重试
      setRemoving(false)
    }
  }

  return (
    <div className="bg-background flex h-full min-h-0 flex-col overflow-hidden rounded-lg border shadow-sm">
      {/* 头部 */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-medium">成员</h3>
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground text-xs">{members.length}</span>
          {onClose && (
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground -mr-1 size-6"
              onClick={onClose}
            >
              <X className="size-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* 列表 */}
      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
        {members.map((m) => (
          <MemberRow
            key={m.id}
            member={m}
            onRequestRemove={onRemove ? () => setPendingRemove(m) : undefined}
          />
        ))}
      </div>

      {/* 招募按钮 */}
      <div className="shrink-0 border-t p-2">
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-foreground w-full justify-start"
          onClick={onRecruit}
        >
          <UserPlus className="size-4" />
          招募成员
        </Button>
      </div>

      <AlertDialog
        open={pendingRemove !== null}
        onOpenChange={(o) => !o && setPendingRemove(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>移除成员「{pendingRemove?.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该成员将从此工作空间移除。历史消息保留，之后可重新招募。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={removing}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={removing}
              onClick={(e) => {
                e.preventDefault()
                handleConfirmRemove()
              }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {removing ? '移除中...' : '移除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ============ 窄 dock（沉浸模式常驻）============

interface MemberDockProps {
  members: RosterMember[]
}

/** hover 离开后延迟关闭，给「从 dock 移到浮卡」留缓冲，避免一移开就收 */
const CLOSE_DELAY_MS = 120

/**
 * 成员 dock（沉浸模式）
 *
 * 贴左常驻窄竖条：头像竖排 + 运行时状态点；高度随成员数撑开、最高半屏。
 * hover 时向右浮出完整成员卡（Popover 走 portal，不被父级 overflow 裁切、
 * 也不挤会话布局）。
 *
 * 纯展示：沉浸模式追求纯净，不带招募 / 踢人等管理动作（成员管理回非沉浸的宽 roster）。
 */
export function MemberDock({ members }: MemberDockProps) {
  const [open, setOpen] = useState(false)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function handleEnter() {
    if (closeTimer.current) clearTimeout(closeTimer.current)
    setOpen(true)
  }
  function handleLeave() {
    closeTimer.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
          className="bg-background flex min-h-44 w-14 shrink-0 flex-col items-center justify-center gap-2 self-center rounded-lg border py-3 shadow-sm"
        >
          {/* pb-1：给状态点 absolute -bottom 的 2px 留地方，否则触发 overflow 滚动条 */}
          <div className="flex max-h-[50vh] flex-col items-center gap-2.5 overflow-x-clip overflow-y-auto px-1 pb-1">
            {members.map((m) => (
              <DockAvatar key={m.id} member={m} />
            ))}
          </div>
        </div>
      </PopoverAnchor>

      {/* hover 浮出完整卡：portal 渲染，向右展开盖在会话上，不挤布局 */}
      <PopoverContent
        side="right"
        align="start"
        sideOffset={8}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onOpenAutoFocus={(e) => e.preventDefault()}
        className="w-64 overflow-hidden p-0"
      >
        <div className="flex max-h-[70vh] flex-col overflow-hidden">
          <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
            <h3 className="text-sm font-medium">成员</h3>
            <span className="text-muted-foreground text-xs">{members.length}</span>
          </div>
          <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
            {members.map((m) => (
              <MemberRow key={m.id} member={m} showStatus />
            ))}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

/** 窄 dock 里的单个成员：头像 + 右下角状态点 */
function DockAvatar({ member }: { member: RosterMember }) {
  const status = memberStatus()
  return (
    <div className="relative shrink-0" title={member.name}>
      <img
        src={member.avatarUrl ?? '/gopher-fcb-glass.png'}
        alt={member.name}
        className="size-8 rounded-full object-cover"
      />
      <span
        className={cn(
          'ring-background absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2',
          STATUS_DOT[status],
        )}
      />
    </div>
  )
}

/**
 * 成员行：头像 + 名称 + 副标题；showStatus 时头像挂运行时状态点。
 * onRequestRemove 传入且为 agent 成员时，hover 露出右侧 X（踢人）。
 */
function MemberRow({
  member,
  showStatus = false,
  onRequestRemove,
}: {
  member: RosterMember
  showStatus?: boolean
  onRequestRemove?: () => void
}) {
  const status = memberStatus()
  const canRemove = member.role === 'agent' && Boolean(onRequestRemove)
  return (
    <div className="group flex items-center gap-2.5 rounded-md px-2 py-1.5 transition hover:bg-muted">
      <div className="relative shrink-0">
        <img
          src={member.avatarUrl ?? '/gopher-fcb-glass.png'}
          alt={member.name}
          className="size-7 rounded-full object-cover"
        />
        {showStatus && (
          <span
            className={cn(
              'ring-background absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2',
              STATUS_DOT[status],
            )}
          />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{member.name}</div>
        <div className="text-muted-foreground truncate text-[11px]">
          {member.subtitle}
        </div>
      </div>
      {canRemove && (
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-destructive size-6 shrink-0 opacity-0 transition group-hover:opacity-100"
          onClick={onRequestRemove}
          title="移除成员"
        >
          <X className="size-3.5" />
        </Button>
      )}
    </div>
  )
}
