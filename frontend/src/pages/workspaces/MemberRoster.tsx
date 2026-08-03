import { useState } from 'react'
import { UserPlus, X } from 'lucide-react'

import { AgentAvatar } from '@/components/brand/AgentAvatar'

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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
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

// ============ 成员头像条（沉浸模式对话区顶部）============

interface MemberStripProps {
  members: RosterMember[]
  onRecruit: () => void
}

/**
 * 成员头像条（沉浸模式）
 *
 * 嵌在沉浸顶栏右侧：成员头像（间隔排列，hover 出品牌淡色 tooltip 显示头像 / 名字 /
 * 角色）+ 招募按钮，不单占一行。成员从左栏卡片降级为这一条，省出对话区宽高；踢人等
 * 管理动作回非沉浸的宽 roster。
 */
export function MemberStrip({ members, onRecruit }: MemberStripProps) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-1.5">
        <div className="flex items-center gap-2">
          {members.map((m) => (
            <Tooltip key={m.id}>
              <TooltipTrigger asChild>
                <AgentAvatar
                  seed={m.seed}
                  src={m.avatarUrl}
                  alt={m.name}
                  className="size-6 cursor-default"
                />
              </TooltipTrigger>
              {/* 品牌淡色底（覆写默认 bg-foreground 深色）+ 同色系文字；箭头一并染成 brand-subtle */}
              <TooltipContent className="bg-brand-subtle text-brand border-brand-border flex items-center gap-2.5 border px-2.5 py-2 [&>svg]:bg-brand-subtle [&>svg]:fill-brand-subtle">
                <AgentAvatar seed={m.seed} src={m.avatarUrl} className="size-7" />
                <div className="min-w-0 leading-tight">
                  <div className="text-brand text-sm font-medium">{m.name}</div>
                  <div className="text-brand/70 text-[11px]">{m.subtitle}</div>
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground size-7"
          onClick={onRecruit}
          title="招募成员"
        >
          <UserPlus className="size-4" />
        </Button>
      </div>
    </TooltipProvider>
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
        <AgentAvatar seed={member.seed} src={member.avatarUrl} alt={member.name} className="size-7" />
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
