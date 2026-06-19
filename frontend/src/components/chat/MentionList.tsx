import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useState,
} from 'react'
import { User } from 'lucide-react'

import { cn } from '@/lib/utils'

/** @mention 候选项 —— 通用形态（不绑 workspace 成员），场景方映射后传入。 */
export interface MentionItem {
  id: string
  label: string
  avatar?: string | null
}

/** 暴露给 TipTap suggestion 的键盘转发接口（上下选 + 回车确认）。 */
export interface MentionListRef {
  onKeyDown: (props: { event: KeyboardEvent }) => boolean
}

interface MentionListProps {
  items: MentionItem[]
  /** TipTap suggestion 提供：选中后插入 mention node。 */
  command: (item: { id: string; label: string }) => void
}

/**
 * @mention 候选浮层 —— 纯展示 + 键盘导航。
 *
 * 定位由 mention-suggestion 用 floating-ui 算好后赋给外层容器，本组件不管定位。
 * 键盘导航靠 useImperativeHandle 暴露 onKeyDown，由 suggestion 的 onKeyDown 转发进来
 * （编辑器仍持有焦点，事件先到编辑器再转发）。
 */
export const MentionList = forwardRef<MentionListRef, MentionListProps>(
  function MentionList({ items, command }, ref) {
    const [selectedIndex, setSelectedIndex] = useState(0)

    // 候选变了（query 变化）→ 高亮回到第一项
    useEffect(() => setSelectedIndex(0), [items])

    const select = (index: number) => {
      const item = items[index]
      if (item) command({ id: item.id, label: item.label })
    }

    useImperativeHandle(ref, () => ({
      onKeyDown: ({ event }) => {
        if (items.length === 0) return false
        if (event.key === 'ArrowUp') {
          setSelectedIndex((i) => (i + items.length - 1) % items.length)
          return true
        }
        if (event.key === 'ArrowDown') {
          setSelectedIndex((i) => (i + 1) % items.length)
          return true
        }
        if (event.key === 'Enter') {
          select(selectedIndex)
          return true
        }
        return false
      },
    }))

    if (items.length === 0) return null

    return (
      <div className="bg-popover text-popover-foreground z-50 max-h-56 w-56 overflow-y-auto rounded-lg border p-1 shadow-md">
        {items.map((item, index) => (
          <button
            key={item.id}
            type="button"
            onClick={() => select(index)}
            className={cn(
              'flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
              index === selectedIndex
                ? 'bg-accent text-accent-foreground'
                : 'hover:bg-accent/50',
            )}
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center overflow-hidden rounded-full">
              {item.avatar ? (
                <img
                  src={item.avatar}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : (
                <User size={12} />
              )}
            </span>
            <span className="truncate">{item.label}</span>
          </button>
        ))}
      </div>
    )
  },
)
