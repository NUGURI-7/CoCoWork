import { useState } from 'react'
import { ChevronDown, MessageSquarePlus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Conversation } from '@/types'
import {
  ConversationList,
  DeleteConversationDialog,
} from './ConversationList'

interface ConversationPanelProps {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  /** 折叠态：只留表头，列表收起 */
  collapsed?: boolean
  onToggleCollapsed?: () => void
}

/**
 * 会话列表常驻面板（沉浸模式左栏下段，spec 占 ~3/5 高）
 *
 * 把顶部 hover 浮窗里的「历史对话」搬成一张常驻卡片：表头 +「新对话」+ 列表。
 * 行渲染复用 ConversationList，删除确认复用 DeleteConversationDialog。可折叠成单条表头。
 */
export function ConversationPanel({
  conversations,
  currentId,
  onSelect,
  onNew,
  onDelete,
  collapsed = false,
  onToggleCollapsed,
}: ConversationPanelProps) {
  // 待确认删除的对话 id（null = 关闭确认弹窗）
  const [confirmId, setConfirmId] = useState<string | null>(null)

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
          对话
        </button>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground -mr-1 size-6"
          onClick={onNew}
          title="新对话"
        >
          <MessageSquarePlus className="size-4" />
        </Button>
      </div>

      {!collapsed && (
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
          <ConversationList
            conversations={conversations}
            currentId={currentId}
            onSelect={onSelect}
            onRequestDelete={setConfirmId}
          />
        </div>
      )}

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
