import { useEffect, useMemo, useState } from 'react'
import { useStore } from 'zustand'
import { ring } from 'ldrs'

import {
  agentConversationResumeEndpoint,
  agentConversationStreamEndpoint,
  listAgentMessages,
} from '@/api/agent-conversation'
import { ChatProvider, useChat } from '@/components/chat/ChatProvider'
import { MessageInput } from '@/components/chat/MessageInput'
import { MessageList } from '@/components/chat/MessageList'
import { useAgentSession } from '@/stores/agent-session'
import { getOrCreateChatStore } from '@/stores/chat-registry'
import { createChatStore, type ChatState } from '@/stores/chat-store'
import type { ApiTextBlock } from '@/types'
import { workspaceMessagesToChatMessages } from '@/pages/workspaces/chat-history'

ring.register()

/** 第一条 user 消息的纯文本 —— 自动起名的依据 */
function selectFirstUserText(s: ChatState): string | null {
  const first = s.messages.find((m) => m.role === 'user')
  if (!first) return null
  const text = first.content
    .filter((b): b is ApiTextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('\n')
    .trim()
  return text || null
}

interface AgentChatProps {
  agentId: string
  agentName: string
  conversationId: string
  /** 新对话：库里还没有，不拉历史；发出第一句话后回调 onStarted 换网址 */
  isNew?: boolean
  onStarted?: () => void
  /** false = Agent 已下线，只能翻看 */
  usable: boolean
}

/**
 * 单 Agent 对话区。与 WorkspaceChat 同一套挂法（store 常驻 chat-registry，切走不断流），
 * 少了成员名册、@ 和拖文件 —— 这里只有员工和这一个 Agent。
 */
export function AgentChat({
  agentId,
  agentName,
  conversationId,
  isNew = false,
  onStarted,
  usable,
}: AgentChatProps) {
  const store = useMemo(
    () =>
      getOrCreateChatStore(conversationId, () =>
        createChatStore({
          endpoint: agentConversationStreamEndpoint(agentId, conversationId),
          sendHistory: false,
          resumeEndpoint: (messageId) =>
            agentConversationResumeEndpoint(agentId, conversationId, messageId),
        }),
      ),
    [agentId, conversationId],
  )
  const [historyLoading, setHistoryLoading] = useState(!isNew)

  // 第一句话 = 入库时刻：先头插进侧栏，再起名，再通知外层换网址
  const firstUserText = useStore(store, selectFirstUserText)
  const ensureTitle = useAgentSession((s) => s.ensureConversationTitle)
  const materialize = useAgentSession((s) => s.materializeConversation)
  useEffect(() => {
    if (!firstUserText) return
    materialize(agentId, conversationId)
    ensureTitle(agentId, conversationId, firstUserText)
    onStarted?.()
  }, [firstUserText, materialize, ensureTitle, onStarted, agentId, conversationId])

  useEffect(() => {
    if (isNew || store.getState().messages.length > 0) {
      setHistoryLoading(false)
      return
    }
    let cancelled = false
    setHistoryLoading(true)
    listAgentMessages(agentId, conversationId)
      .then((msgs) => {
        if (!cancelled) store.getState().hydrate(workspaceMessagesToChatMessages(msgs))
      })
      .catch(() => {
        // 拦截器已 toast；拉不到也放开
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [store, agentId, conversationId, isNew])

  if (historyLoading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  return (
    <ChatProvider store={store}>
      <AgentChatBody agentName={agentName} usable={usable} />
    </ChatProvider>
  )
}

function AgentChatBody({ agentName, usable }: { agentName: string; usable: boolean }) {
  const isEmpty = useChat((s) => s.messages.length === 0)
  return (
    <>
      {isEmpty ? (
        <div className="text-muted-foreground/70 flex flex-1 items-center justify-center px-4 text-center text-sm">
          {usable ? `跟「${agentName}」说点什么` : '这个 Agent 已下线'}
        </div>
      ) : (
        <MessageList />
      )}
      <MessageInput disabled={!usable} disabledHint="这个 Agent 已下线，只能查看以前的对话" />
    </>
  )
}
