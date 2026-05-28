import { useNavigate } from '@tanstack/react-router'
import { X, MoreHorizontal } from 'lucide-react'
import type { StoreApi, UseBoundStore } from 'zustand'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useHorizontalWheelScroll } from '@/hooks/use-horizontal-wheel-scroll'
import type { Tab, TabsState } from '@/stores/tab-store'

interface TabBarProps {
  useStore: UseBoundStore<StoreApi<TabsState>>
}

export function TabBar({ useStore }: TabBarProps) {
  const tabs = useStore((s) => s.tabs)
  const activePath = useStore((s) => s.activePath)
  const activate = useStore((s) => s.activate)
  const close = useStore((s) => s.close)
  const closeOthers = useStore((s) => s.closeOthers)
  const closeAll = useStore((s) => s.closeAll)
  const navigate = useNavigate()
  const scrollRef = useHorizontalWheelScroll<HTMLDivElement>()

  function handleClick(tab: Tab) {
    activate(tab.path)
    navigate({ to: tab.path })
  }

  function handleClose(e: React.MouseEvent, tab: Tab) {
    e.stopPropagation()
    if (tab.pinned) return
    const currentActive = useStore.getState().activePath
    close(tab.path)
    if (currentActive === tab.path) {
      const newActive = useStore.getState().activePath
      navigate({ to: newActive })
    }
  }

  const active = (path: string) => activePath === path

  return (
    <div className="relative flex h-10 items-center border-b">
      <div
        ref={scrollRef}
        className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.path}
              onClick={() => handleClick(tab)}
              className={cn(
                'group relative flex h-7 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-sm transition-colors',
                'hover:bg-accent/60 hover:text-accent-foreground',
                active(tab.path)
                  ? 'bg-brand-subtle font-medium text-brand'
                  : 'text-muted-foreground',
              )}
            >
              {Icon && (
                <Icon
                  className={cn(
                    'size-3.5 shrink-0',
                    active(tab.path) ? 'text-brand' : 'text-muted-foreground/70',
                  )}
                />
              )}
              <span className="max-w-24 truncate">{tab.title}</span>
              {!tab.pinned && (
                <X
                  className={cn(
                    'size-3.5 shrink-0 rounded-sm transition-opacity',
                    'hover:bg-muted-foreground/20',
                    active(tab.path)
                      ? 'opacity-60 hover:opacity-100'
                      : 'opacity-0 group-hover:opacity-60 group-hover:hover:opacity-100',
                  )}
                  onClick={(e) => handleClose(e, tab)}
                />
              )}
              {/* 底部指示条 */}
              {active(tab.path) && (
                <span className="absolute -bottom-px left-2 right-2 h-0.5 rounded-full bg-brand" />
              )}
            </button>
          )
        })}
      </div>

      {tabs.length > 1 && (
        <div className="shrink-0 border-l px-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="size-7">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={closeOthers}>关闭其他标签</DropdownMenuItem>
              <DropdownMenuItem onClick={closeAll}>关闭所有标签</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </div>
  )
}
