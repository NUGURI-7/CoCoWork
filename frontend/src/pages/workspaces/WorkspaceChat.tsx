import { useEffect, useMemo, useState } from 'react'
import { ring } from 'ldrs'

import { conversationStreamEndpoint, listMessages } from '@/api/workspace'
import { ChatProvider, useChat } from '@/components/chat/ChatProvider'
import { MessageInput } from '@/components/chat/MessageInput'
import { MessageList } from '@/components/chat/MessageList'
import { getOrCreateChatStore } from '@/stores/chat-registry'
import { createChatStore } from '@/stores/chat-store'
import { workspaceMessagesToChatMessages } from './chat-history'

ring.register()

interface WorkspaceChatProps {
  workspaceId: string
  conversationId: string
  /** 管家是否已配 chat 模型；未配置时禁发 + 提示去右栏配置 */
  supervisorReady: boolean
}

/**
 * 主对话区 —— workspace 真对话（supervisor 应答）。
 *
 * 架构与 Playground 同款 mount，三点差异：
 * - sendHistory: false —— 历史真源在 DB，后端自己拼，body 只送当前一句
 * - 进对话先 listMessages + hydrate 回放历史；加载完成前不渲染输入框（天然禁发）
 * - store 不随组件挂载，而是从 chat-registry 常驻架子按 conversationId 取：
 *   切对话组件销毁，但桶留在架子上、流继续 →「切走不断流」。空桶才灌历史，
 *   非空（灌过 / 后台在跑）直接复用。架子在离开工作空间时整体回收。
 *
 * mock 双轨路由 / @mention popover 已退役 —— d-3 @ 路由片按真设计重做
 * （mentioned_member_ids 要进请求 body，输入框届时扩展）。
 */
export function WorkspaceChat({
  workspaceId,
  conversationId,
  supervisorReady,
}: WorkspaceChatProps) {
  const endpoint = conversationStreamEndpoint(workspaceId, conversationId)
  const store = useMemo(
    () =>
      getOrCreateChatStore(conversationId, () => createChatStore({ endpoint, sendHistory: false })),
    [conversationId, endpoint],
  )
  const [historyLoading, setHistoryLoading] = useState(true)

  useEffect(() => {
    // 桶已经有内容（之前灌过历史 / 正在后台跑）→ 不重灌，直接放行
    if (store.getState().messages.length > 0) {
      setHistoryLoading(false)
      return
    }

    let cancelled = false
    setHistoryLoading(true)

    listMessages(workspaceId, conversationId)
      .then((msgs) => {
        if (cancelled) return
        store.getState().hydrate(workspaceMessagesToChatMessages(msgs))
      })
      .catch(() => {
        // 拦截器已 toast；历史拉不到也放开输入
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })

    return () => {
      cancelled = true
      // 不再 reset()：切走时桶留在架子上、流继续。组件拆了，不碰桶。
    }
  }, [store, workspaceId, conversationId])

  if (historyLoading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  return (
    <ChatProvider store={store}>
      <WorkspaceChatBody supervisorReady={supervisorReady} />
    </ChatProvider>
  )
}

function WorkspaceChatBody({ supervisorReady }: { supervisorReady: boolean }) {
  const isEmpty = useChat((s) => s.messages.length === 0)

  return (
    <>
      {isEmpty ? <EmptyHint /> : <MessageList />}
      <MessageInput
        disabled={!supervisorReady}
        disabledHint="先在右侧「空间配置」里给管家选一个对话模型"
      />
    </>
  )
}

function EmptyHint() {
  return (
    <div className="text-muted-foreground/70 flex flex-1 items-center justify-center px-4 text-center text-sm">
      跟管家说点什么，开始这个空间的协作
    </div>
  )
}
