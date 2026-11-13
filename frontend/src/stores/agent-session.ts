/**
 * 单 Agent 会话 store —— 跨路由共享「能用的 Agent 列表 + 当前 Agent + 它的会话列表」。
 *
 * 与 workspace-session 对称：全局侧栏切到 Agent 模式时读这里。activeAgentId 持久化
 * （last-used），下次切回 Agent 模式还原上次那个。会话流的实时状态仍在
 * stream-status / chat-registry，本 store 只管列表数据与归属。
 */
import { toast } from 'sonner'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  deleteAgentConversation,
  generateAgentConversationTitle,
  listAgentConversations,
  listAvailableAgents,
  updateAgentConversation,
} from '@/api/agent-conversation'
import { disposeChatStore } from '@/stores/chat-registry'
import type { AgentBrief, AgentConversation } from '@/types'

/** 占位标题取用户那句话的前几个字 —— 只为填满起名那 1~2 秒的空窗 */
const TITLE_PLACEHOLDER_CHARS = 10

/** 正在起名的会话 id —— 并发闸，不参与渲染所以不进 store（同 workspace-session） */
const titleInFlight = new Set<string>()

function withoutKey(map: Record<string, string>, key: string) {
  return Object.fromEntries(Object.entries(map).filter(([id]) => id !== key))
}

interface AgentSessionState {
  agents: AgentBrief[]
  agentsLoaded: boolean
  /** 当前选中的 Agent —— 持久化（last-used） */
  activeAgentId: string | null
  /** 当前 Agent 的会话列表 */
  conversations: AgentConversation[]
  /** conversations 当前归属哪个 Agent */
  convLoadedFor: string | null
  convLoadingFor: string | null
  /** 会话 id → 起名期间的占位标题。绝不写进 conversations[].title（理由同 workspace-session） */
  titlePlaceholders: Record<string, string>

  /** 拉能用的 Agent，并校正 activeAgentId（失效 / 为空落到第一个） */
  loadAgents: () => Promise<void>
  /** 切到某个 Agent：换 activeAgentId + 加载其会话（id 不变则仅确保已加载） */
  setActiveAgent: (agentId: string) => void
  loadConversations: (agentId: string, opts?: { force?: boolean }) => Promise<void>
  ensureConversationTitle: (
    agentId: string,
    conversationId: string,
    sourceText: string,
  ) => Promise<void>
  /** 新对话发出第一句话：头插进列表（后端在同一个请求里建库）；已在列表里则不动 */
  materializeConversation: (agentId: string, conversationId: string) => void
  renameConversation: (agentId: string, conversationId: string, title: string) => Promise<void>
  deleteConversation: (agentId: string, conversationId: string) => Promise<void>
}

export const useAgentSession = create<AgentSessionState>()(
  persist(
    (set, get) => ({
      agents: [],
      agentsLoaded: false,
      activeAgentId: null,
      conversations: [],
      convLoadedFor: null,
      convLoadingFor: null,
      titlePlaceholders: {},

      loadAgents: async () => {
        let agents: AgentBrief[]
        try {
          agents = await listAvailableAgents()
        } catch {
          return // 拦截器已 toast
        }
        set({ agents, agentsLoaded: true })
        const { activeAgentId } = get()
        if (activeAgentId && agents.some((a) => a.id === activeAgentId)) {
          get().loadConversations(activeAgentId)
        } else if (agents.length > 0) {
          get().setActiveAgent(agents[0].id)
        } else {
          set({ activeAgentId: null, conversations: [], convLoadedFor: null })
        }
      },

      setActiveAgent: (agentId) => {
        if (get().activeAgentId === agentId) {
          get().loadConversations(agentId)
          return
        }
        set({ activeAgentId: agentId, conversations: [], convLoadedFor: null })
        get().loadConversations(agentId)
      },

      loadConversations: async (agentId, opts) => {
        const { convLoadedFor, convLoadingFor } = get()
        if (convLoadingFor === agentId) return
        if (!opts?.force && convLoadedFor === agentId) return
        set({ convLoadingFor: agentId })

        let conversations: AgentConversation[]
        try {
          conversations = await listAgentConversations(agentId)
        } catch {
          set((s) => ({ convLoadingFor: s.convLoadingFor === agentId ? null : s.convLoadingFor }))
          return
        }
        // 加载期间可能已切到别的 Agent：只在仍是当前 Agent 时写入
        if (get().activeAgentId !== agentId) {
          set((s) => ({ convLoadingFor: s.convLoadingFor === agentId ? null : s.convLoadingFor }))
          return
        }
        set({ conversations, convLoadedFor: agentId, convLoadingFor: null })
      },

      ensureConversationTitle: async (agentId, conversationId, sourceText) => {
        if (get().conversations.find((c) => c.id === conversationId)?.title) return
        if (titleInFlight.has(conversationId)) return
        const text = sourceText.trim()
        if (!text) return

        titleInFlight.add(conversationId)
        set((s) => ({
          titlePlaceholders: {
            ...s.titlePlaceholders,
            [conversationId]: text.slice(0, TITLE_PLACEHOLDER_CHARS),
          },
        }))

        let title: string
        try {
          ;({ title } = await generateAgentConversationTitle(agentId, conversationId, text))
        } catch {
          return // 静默：库里仍是空，下次进对话再试；占位留着
        } finally {
          titleInFlight.delete(conversationId)
        }

        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === conversationId ? { ...c, title } : c,
          ),
          titlePlaceholders: withoutKey(s.titlePlaceholders, conversationId),
        }))
      },

      materializeConversation: (agentId, conversationId) => {
        const { activeAgentId, conversations } = get()
        if (activeAgentId !== agentId) return
        if (conversations.some((c) => c.id === conversationId)) return
        const now = new Date().toISOString()
        set({
          conversations: [
            { id: conversationId, agent_id: agentId, title: '', created_at: now, updated_at: now },
            ...conversations,
          ],
        })
      },

      renameConversation: async (agentId, conversationId, title) => {
        try {
          await updateAgentConversation(agentId, conversationId, { title })
        } catch {
          toast.error('重命名失败')
          return
        }
        if (get().activeAgentId !== agentId) return
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === conversationId ? { ...c, title } : c,
          ),
          titlePlaceholders: withoutKey(s.titlePlaceholders, conversationId),
        }))
      },

      deleteConversation: async (agentId, conversationId) => {
        try {
          await deleteAgentConversation(agentId, conversationId)
        } catch {
          return
        }
        disposeChatStore(conversationId)
        titleInFlight.delete(conversationId)
        if (get().activeAgentId === agentId) {
          set((s) => ({
            conversations: s.conversations.filter((c) => c.id !== conversationId),
            titlePlaceholders: withoutKey(s.titlePlaceholders, conversationId),
          }))
        }
      },
    }),
    {
      name: 'agent-session',
      partialize: (s) => ({ activeAgentId: s.activeAgentId }),
    },
  ),
)

/** 「算显示标题」的函数 —— 真标题 → 占位 → 新对话（同 workspace-session 的同名函数） */
export function useAgentConversationTitle() {
  const placeholders = useAgentSession((s) => s.titlePlaceholders)
  return (conv: Pick<AgentConversation, 'id' | 'title'>) =>
    conv.title || placeholders[conv.id] || '新对话'
}
