import { useRef, useState, type ReactNode } from 'react'
import { Check, ChevronDown, MessageSquarePlus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import type { Conversation } from '@/types'

interface ConversationSwitcherProps {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  /** 右侧「新对话」之后的尾槽（沉浸模式放退出按钮，平时不传） */
  trailing?: ReactNode
}

function timeAgo(s: string): string {
  const diff = Date.now() - new Date(s).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 60) return `${Math.max(m, 1)} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

/**
 * 主对话区顶部 conversation 切换条
 *
 * - 左：当前对话标题 + 下拉，展开历史列表
 * - 右：「新对话」按钮，push 一条新 conversation 到 store + 自动切换
 */
export function ConversationSwitcher({
  conversations,
  currentId,
  onSelect,
  onNew,
  trailing,
}: ConversationSwitcherProps) {
  const [open, setOpen] = useState(false)
  // hover-intent：离开后延迟关闭，给「从标题移到下拉」留缓冲，避免一移开就收
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 按更新时间倒序
  const sorted = [...conversations].sort(
    (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
  )
  const current = sorted.find((c) => c.id === currentId) ?? sorted[0]

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
            {sorted.length === 0 ? (
              <div className="text-muted-foreground px-2 py-3 text-center text-xs">
                还没有对话
              </div>
            ) : (
              sorted.map((c) => {
                const isActive = c.id === currentId
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => handleSelect(c.id)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left',
                      isActive ? 'bg-brand-subtle' : 'hover:bg-muted',
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div
                        className={cn(
                          'truncate text-sm',
                          isActive && 'text-brand font-medium',
                        )}
                      >
                        {c.title || '新对话'}
                      </div>
                      <div className="text-muted-foreground text-[11px]">
                        {timeAgo(c.updated_at)}
                      </div>
                    </div>
                    {isActive && <Check className="text-brand size-3.5 shrink-0" />}
                  </button>
                )
              })
            )}
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
    </div>
  )
}
