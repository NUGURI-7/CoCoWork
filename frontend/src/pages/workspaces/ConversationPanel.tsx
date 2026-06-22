import { useState } from 'react'
import { MessageSquarePlus } from 'lucide-react'

import { Button } from '@/components/ui/button'
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
}

/**
 * 会话列表常驻面板（沉浸模式左栏）
 *
 * 表头「对话」+「新对话」+ 列表，常驻满高。收起 / 展开由外部整块控制（沉浸顶栏的
 * 开关按钮；收起 = 整个面板不渲染、宽度 0），面板自己不再做折叠。
 * 行渲染复用 ConversationList，删除确认复用 DeleteConversationDialog。
 */
export function ConversationPanel({
  conversations,
  currentId,
  onSelect,
  onNew,
  onDelete,
}: ConversationPanelProps) {
  // 待确认删除的对话 id（null = 关闭确认弹窗）
  const [confirmId, setConfirmId] = useState<string | null>(null)

  return (
    <div className="bg-background flex h-full min-h-0 flex-col overflow-hidden rounded-lg border shadow-sm">
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-medium">对话</h3>
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

      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
        <ConversationList
          conversations={conversations}
          currentId={currentId}
          onSelect={onSelect}
          onRequestDelete={setConfirmId}
        />
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
