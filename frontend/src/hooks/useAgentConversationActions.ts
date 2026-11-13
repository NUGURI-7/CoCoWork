/**
 * 单 Agent 会话操作 —— 选会话 / 新对话 / 删除 / 改名连同导航收在一处，供侧栏用。
 * 与 useConversationActions（工作空间）对称；当前会话 id 的真源在网址。
 */
import { useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'

import { useCurrentConversationId } from '@/hooks/useConversationActions'
import { useAgentSession } from '@/stores/agent-session'

export function useAgentConversationActions() {
  const navigate = useNavigate()
  const activeAgentId = useAgentSession((s) => s.activeAgentId)
  const conversations = useAgentSession((s) => s.conversations)
  const deleteConversation = useAgentSession((s) => s.deleteConversation)
  const renameConversation = useAgentSession((s) => s.renameConversation)
  const currentConvId = useCurrentConversationId()

  const select = useCallback(
    (conversationId: string) => {
      if (!activeAgentId) return
      navigate({
        to: '/chat/$agentId/c/$conversationId',
        params: { agentId: activeAgentId, conversationId },
      })
    },
    [navigate, activeAgentId],
  )

  /** 打开新对话页（/new）。此时不入库，发出第一句话时后端才建。 */
  const createAndOpen = useCallback(() => {
    if (!activeAgentId) return
    navigate({ to: '/chat/$agentId/new', params: { agentId: activeAgentId } })
  }, [activeAgentId, navigate])

  /** 删的是当前会话 → 跳到最近一条剩余，一条不剩就去新对话页 */
  const remove = useCallback(
    async (conversationId: string) => {
      if (!activeAgentId) return
      const deletingCurrent = conversationId === currentConvId
      const remaining = conversations.filter((c) => c.id !== conversationId)
      await deleteConversation(activeAgentId, conversationId)
      if (!deletingCurrent) return
      const next = [...remaining].sort(
        (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
      )[0]
      if (next) {
        navigate({
          to: '/chat/$agentId/c/$conversationId',
          params: { agentId: activeAgentId, conversationId: next.id },
          replace: true,
        })
      } else {
        navigate({ to: '/chat/$agentId/new', params: { agentId: activeAgentId }, replace: true })
      }
    },
    [activeAgentId, currentConvId, conversations, deleteConversation, navigate],
  )

  const rename = useCallback(
    async (conversationId: string, title: string) => {
      const next = title.trim()
      if (!activeAgentId || !next) return
      await renameConversation(activeAgentId, conversationId, next)
    },
    [activeAgentId, renameConversation],
  )

  return { currentConvId, select, createAndOpen, remove, rename }
}
