import { Crown, UserPlus, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { WorkspaceMember } from '@/types'

interface MemberRosterProps {
  members: WorkspaceMember[]
  onRecruit: () => void
  /** 传入则在头部显示关闭按钮 */
  onClose?: () => void
}

/**
 * 通讯录（左栏，spec §5.3）
 *
 * 管家固定第一位；其余成员按招募顺序展示。
 * v0 列表点击不展开实例详情（spec §5.3 留给后续切片）。
 */
export function MemberRoster({ members, onRecruit, onClose }: MemberRosterProps) {
  // 管家固定排第一，其余保持顺序
  const sorted = [...members].sort((a, b) => {
    if (a.role === 'supervisor') return -1
    if (b.role === 'supervisor') return 1
    return 0
  })

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
        {sorted.map((m) => (
          <MemberRow key={m.id} member={m} />
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
    </div>
  )
}

function MemberRow({ member }: { member: WorkspaceMember }) {
  const isSupervisor = member.role === 'supervisor'
  return (
    <div
      className={cn(
        'flex items-center gap-2.5 rounded-md px-2 py-1.5 transition hover:bg-background',
      )}
    >
      <div
        className="flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-medium text-white"
        style={{ backgroundColor: member.avatar_color }}
      >
        {isSupervisor ? <Crown className="size-3.5" /> : member.name.slice(0, 1)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{member.name}</div>
        <div className="text-muted-foreground truncate text-[11px]">
          {isSupervisor
            ? '调度'
            : `${member.source === 'template' ? '模板' : 'Agent'} · ${member.source_name}`}
        </div>
      </div>
    </div>
  )
}
