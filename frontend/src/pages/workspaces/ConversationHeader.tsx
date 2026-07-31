import type { ReactNode } from 'react'

import { useStreamStatusStore } from '@/stores/stream-status'
import { useConversationTitle } from '@/stores/workspace-session'
import type { Conversation } from '@/types'
import { StatusDot } from './ConversationList'

interface ConversationHeaderProps {
  conversations: Conversation[]
  currentId: string | null
  /** 沉浸模式：全宽极简顶栏（leading + 标题 + actions + trailing）；否则细标题条 */
  immersive?: boolean
  /** 标题左侧引导槽（沉浸放全局侧栏收起钮） */
  leading?: ReactNode
  /** 标题右侧、尾槽之前的槽（沉浸放成员头像条） */
  actions?: ReactNode
  /** 行尾槽（沉浸放产物 / 退出按钮） */
  trailing?: ReactNode
}

/**
 * 对话区顶部标题条 —— 只显示当前会话标题 + 实时状态点。
 *
 * 会话切换已搬到全局侧边栏，这里不再带下拉列表 / 新建按钮。
 * - 非沉浸：细标题条（带下边框）
 * - 沉浸：全宽极简顶栏，承载 leading / actions / trailing 三槽
 */
export function ConversationHeader({
  conversations,
  currentId,
  immersive = false,
  leading,
  actions,
  trailing,
}: ConversationHeaderProps) {
  const statuses = useStreamStatusStore((s) => s.statuses)
  const titleOf = useConversationTitle()
  const sorted = [...conversations].sort(
    (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
  )
  const current = sorted.find((c) => c.id === currentId) ?? sorted[0]
  const title = current ? titleOf(current) : '无对话'
  const status = current ? statuses[current.id] ?? 'idle' : 'idle'

  if (immersive) {
    return (
      <div className="flex shrink-0 items-center justify-between gap-2 px-2 py-1">
        <div className="flex min-w-0 items-center gap-2">
          {leading}
          <span className="truncate text-sm font-medium">{title}</span>
          {current && <StatusDot status={status} />}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          {trailing && <div className="flex items-center gap-1">{trailing}</div>}
        </div>
      </div>
    )
  }

  return (
    <div className="flex shrink-0 items-center gap-1.5 border-b px-4 py-2.5">
      <span className="truncate text-sm font-medium">{title}</span>
      {current && <StatusDot status={status} />}
    </div>
  )
}
