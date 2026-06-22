import { useRef, useState, type ReactNode } from 'react'
import { ChevronDown, MessageSquarePlus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { useStreamStatusStore } from '@/stores/stream-status'
import type { Conversation } from '@/types'
import {
  ConversationList,
  DeleteConversationDialog,
  StatusDot,
} from './ConversationList'

interface ConversationSwitcherProps {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  /** 右侧「新对话」之后的尾槽（沉浸模式放退出按钮，平时不传） */
  trailing?: ReactNode
  /** 沉浸模式右侧、尾槽之前的槽（放成员头像条），仅沉浸用 */
  actions?: ReactNode
  /** 沉浸模式：会话列表已常驻左栏 → 标题静态化、隐藏下拉与「新对话」，只留 trailing */
  immersive?: boolean
  /** 沉浸模式标题左侧的引导槽（放全局侧栏收起按钮），仅沉浸全宽顶栏用 */
  leading?: ReactNode
}

/**
 * 主对话区顶部 conversation 切换条
 *
 * - 非沉浸：左侧当前标题 + 下拉展开历史列表，右侧「新对话」+ 尾槽
 * - 沉浸：列表已搬到左栏常驻面板 → 顶栏只剩静态标题 + 尾槽（产物 / 退出）
 */
export function ConversationSwitcher({
  conversations,
  currentId,
  onSelect,
  onNew,
  onDelete,
  trailing,
  immersive = false,
  leading,
  actions,
}: ConversationSwitcherProps) {
  const [open, setOpen] = useState(false)
  // 待确认删除的对话 id —— 单个受控 AlertDialog（放 Popover 外，portaled 不受 hover 收起影响）
  const [confirmId, setConfirmId] = useState<string | null>(null)
  // hover-intent：离开后延迟关闭，给「从标题移到下拉」留缓冲，避免一移开就收
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 每条对话的实时状态（registry 写入）—— 画状态点
  const statuses = useStreamStatusStore((s) => s.statuses)
  // 按更新时间倒序，取当前/兜底首条
  const sorted = [...conversations].sort(
    (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
  )
  const current = sorted.find((c) => c.id === currentId) ?? sorted[0]

  // 沉浸模式：会话列表已在左栏常驻 → 退化为全宽极简顶栏（leading 收起钮 + 静态标题 + 尾槽）
  if (immersive) {
    return (
      <div className="flex shrink-0 items-center justify-between gap-2 border-b px-2 py-2">
        <div className="flex min-w-0 items-center gap-2">
          {leading}
          <span className="truncate text-sm font-medium">
            {current ? current.title || '新对话' : '无对话'}
          </span>
          {current && <StatusDot status={statuses[current.id] ?? 'idle'} />}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          {trailing && <div className="flex items-center gap-1">{trailing}</div>}
        </div>
      </div>
    )
  }

  function handleEnter() {
    if (closeTimer.current) clearTimeout(closeTimer.current)
    setOpen(true)
  }
  function handleLeave() {
    closeTimer.current = setTimeout(() => setOpen(false), 120)
  }
  function handleSelect(id: string) {
    onSelect(id)
    setOpen(false)
  }
  function handleNew() {
    onNew()
    setOpen(false)
  }

  return (
    <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverAnchor asChild>
          <button
            type="button"
            onMouseEnter={handleEnter}
            onMouseLeave={handleLeave}
            className="hover:bg-muted flex min-w-0 items-center gap-1.5 rounded-md px-2 py-1 text-left transition"
          >
            <span className="truncate text-sm font-medium">
              {/* 空串 = 标题待生成（首轮对话后系统补） */}
              {current ? current.title || '新对话' : '无对话'}
            </span>
            {current && <StatusDot status={statuses[current.id] ?? 'idle'} />}
            <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
          </button>
        </PopoverAnchor>
        <PopoverContent
          align="start"
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="w-72 p-1"
        >
          <div className="text-muted-foreground px-2 py-1.5 text-[11px] font-medium tracking-wide uppercase">
            历史对话
          </div>
          <div className="max-h-64 space-y-0.5 overflow-y-auto">
            <ConversationList
              conversations={conversations}
              currentId={currentId}
              onSelect={handleSelect}
              onRequestDelete={(id) => {
                setConfirmId(id)
                setOpen(false)
              }}
            />
          </div>
        </PopoverContent>
      </Popover>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleNew}
          className="text-muted-foreground hover:text-foreground"
        >
          <MessageSquarePlus className="size-4" />
          新对话
        </Button>
        {trailing}
      </div>

      <DeleteConversationDialog
        conversation={conversations.find((c) => c.id === confirmId)}
        open={confirmId !== null}
        onOpenChange={(o) => !o && setConfirmId(null)}
        onConfirm={() => {
          if (confirmId) onDelete(confirmId)
          setConfirmId(null)
        }}
      />
    </div>
  )
}
