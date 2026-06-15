import { useState } from 'react'
import { ChevronDown, UserPlus, X } from 'lucide-react'

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
              variant="destructive"
            >
              {removing ? '移除中...' : '移除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ============ 成员面板（沉浸模式左栏上段，纯展示）============

interface MemberPanelProps {
  members: RosterMember[]
  /** 折叠态：只留表头，body 收起 */
  collapsed?: boolean
  onToggleCollapsed?: () => void
}

/**
 * 成员面板（沉浸模式）
 *
 * 满宽常驻卡片：表头「成员 N」+ 成员行列表（头像 + 名字 + 副标题 + 运行时状态点），
 * 与下方会话面板同宽、各自独立成卡。纵向占左栏上段（~2/5 高）。可折叠成单条表头。
 *
 * 纯展示：沉浸模式追求纯净，不带招募 / 踢人等管理动作（成员管理回非沉浸的宽 roster）。
 */
export function MemberPanel({
  members,
  collapsed = false,
  onToggleCollapsed,
}: MemberPanelProps) {
  return (
    <div
      className={cn(
        'bg-background flex flex-col overflow-hidden rounded-lg border shadow-sm',
        collapsed ? 'h-auto' : 'h-full min-h-0',
      )}
    >
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="hover:text-foreground -ml-1 flex items-center gap-1.5 rounded px-1 text-sm font-medium"
        >
          <ChevronDown
            className={cn(
              'text-muted-foreground size-3.5 shrink-0 transition-transform',
              collapsed && '-rotate-90',
            )}
          />
          成员
        </button>
        <span className="text-muted-foreground text-xs">{members.length}</span>
      </div>
      {!collapsed && (
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
          {members.map((m) => (
            <MemberRow key={m.id} member={m} showStatus />
          ))}
        </div>
      )}
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
