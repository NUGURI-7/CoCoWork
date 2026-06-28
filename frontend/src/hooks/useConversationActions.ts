/**
 * 会话操作 hook —— 把「选会话 / 新建 / 删除」连同导航收敛到一处，供侧栏会话块与
 * 工作空间页共用，避免两边各写一套导航逻辑。
 *
 * 数据真源在 workspace-session store；当前会话 id 真源在 URL（子路由
 * /c/$conversationId 的 path 参数）。本 hook 只负责「改 store + 改 URL」的编排。
 */
import { useCallback } from 'react'
import { useNavigate, useRouterState } from '@tanstack/react-router'

import { useWorkspaceSession } from '@/stores/workspace-session'

/** 从路由匹配树里读当前会话 id（落在 /c/$conversationId 时有值，否则 null）。 */
export function useCurrentConversationId(): string | null {
  return useRouterState({
    select: (s) => {
      for (const m of s.matches) {
        const p = m.params as { conversationId?: string }
        if (p?.conversationId) return p.conversationId
      }
      return null
    },
  })
}

export function useConversationActions() {
  const navigate = useNavigate()
  const activeWorkspaceId = useWorkspaceSession((s) => s.activeWorkspaceId)
  const conversations = useWorkspaceSession((s) => s.conversations)
  const createConversation = useWorkspaceSession((s) => s.createConversation)
  const deleteConversation = useWorkspaceSession((s) => s.deleteConversation)
  const currentConvId = useCurrentConversationId()

  /** 选中某会话 = 跳到它的对话路由（前进后退能在会话间走）。 */
  const select = useCallback(
    (conversationId: string) => {
      if (!activeWorkspaceId) return
      navigate({
        to: '/workspaces/$workspaceId/c/$conversationId',
        params: { workspaceId: activeWorkspaceId, conversationId },
      })
    },
    [navigate, activeWorkspaceId],
  )

  /** 新建会话并打开。 */
  const createAndOpen = useCallback(async () => {
    if (!activeWorkspaceId) return
    const created = await createConversation(activeWorkspaceId)
    if (created) {
      navigate({
        to: '/workspaces/$workspaceId/c/$conversationId',
        params: { workspaceId: activeWorkspaceId, conversationId: created.id },
      })
    }
  }, [activeWorkspaceId, createConversation, navigate])

  /**
   * 删除会话。删的不是当前会话 → 只从列表移除；删的是当前会话 → 跳到最近一条剩余，
   * 一条不剩则回空间 index（页面 entry effect 会自动补一条并跳过去）。
   */
  const remove = useCallback(
    async (conversationId: string) => {
      if (!activeWorkspaceId) return
      const deletingCurrent = conversationId === currentConvId
      const remaining = conversations.filter((c) => c.id !== conversationId)
      await deleteConversation(activeWorkspaceId, conversationId)
      if (!deletingCurrent) return
      if (remaining.length > 0) {
        const next = [...remaining].sort(
          (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
        )[0]
        navigate({
          to: '/workspaces/$workspaceId/c/$conversationId',
          params: { workspaceId: activeWorkspaceId, conversationId: next.id },
          replace: true,
        })
      } else {
        navigate({
          to: '/workspaces/$workspaceId',
          params: { workspaceId: activeWorkspaceId },
          replace: true,
        })
      }
    },
    [activeWorkspaceId, currentConvId, conversations, deleteConversation, navigate],
  )

  return { currentConvId, select, createAndOpen, remove }
}
