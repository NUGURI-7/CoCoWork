import { useCallback, useState, type ComponentType, type ReactNode } from 'react'
import { Check, Copy } from 'lucide-react'

import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

/** 单个操作项定义 —— action line 数据驱动，加新操作只往数组里加一项。 */
export interface MessageAction {
  key: string
  /** 默认态图标 */
  icon: ComponentType<{ size?: number | string }>
  /** 触发后短暂展示的反馈图标（如复制成功的 ✓）；不传则无切换反馈 */
  activeIcon?: ComponentType<{ size?: number | string }>
  /** 无障碍 / tooltip 文案 */
  label: string
  /** 点击回调；返回 false 视为失败，不触发反馈态 */
  onClick: () => boolean | void | Promise<boolean | void>
}

/** 反馈态持续时长（ms） */
const FEEDBACK_MS = 1500

function ActionButton({ action }: { action: MessageAction }) {
  const [active, setActive] = useState(false)

  const handleClick = useCallback(async () => {
    const ok = await action.onClick()
    if (ok === false) return
    if (!action.activeIcon) return
    setActive(true)
    setTimeout(() => setActive(false), FEEDBACK_MS)
  }, [action])

  const Icon = active && action.activeIcon ? action.activeIcon : action.icon

  return (
    <button
      type="button"
      onClick={handleClick}
      title={action.label}
      aria-label={action.label}
      className="text-muted-foreground hover:text-foreground hover:bg-muted flex h-7 w-7 cursor-pointer items-center justify-center rounded-md transition-colors"
    >
      <Icon size={14} />
    </button>
  )
}

/**
 * 消息操作栏（action line）—— 一条可扩展的操作按钮容器。
 *
 * 数据驱动：通过 `actions` 数组渲染，复制只是其中一项，后续「重新生成 /
 * 引用 / 朗读」等只需往数组里加项，无需改布局。
 *
 * 默认半透明，父级 hover（需父容器加 `group` 类）时浮现，不抢视觉。
 */
export function MessageActions({
  actions,
  align = 'left',
  className,
  extra,
}: {
  actions: MessageAction[]
  align?: 'left' | 'right'
  className?: string
  /** 非按钮的附挂内容（如本轮 token 消耗），跟在按钮后面同排显示 */
  extra?: ReactNode
}) {
  if (actions.length === 0 && !extra) return null

  return (
    <div
      className={cn(
        'flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100',
        align === 'right' && 'justify-end',
        className,
      )}
    >
      {actions.map((action) => (
        <ActionButton key={action.key} action={action} />
      ))}
      {extra}
    </div>
  )
}

/** 复制操作的便捷构造器 —— 复用复制+✓反馈逻辑。 */
export function copyAction(getText: () => string): MessageAction {
  return {
    key: 'copy',
    icon: Copy,
    activeIcon: Check,
    label: '复制',
    onClick: () => copyText(getText()),
  }
}
