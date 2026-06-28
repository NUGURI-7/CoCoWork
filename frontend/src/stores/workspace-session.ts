/**
 * 全局工作会话 store —— 跨路由共享「当前工作空间 + 其会话列表」。
 *
 * 会话列表从工作空间详情页上提到这里，让全局侧边栏（渲染在路由树之外）也能列出会话，
 * 做成 ChatGPT 式常驻。activeWorkspaceId 持久化到 localStorage（last-used），进 App
 * 默认还原上次的空间。会话流的实时状态仍在 stream-status / chat-registry，本 store
 * 只管列表数据与归属。
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  createConversation as apiCreateConversation,
  deleteConversation as apiDeleteConversation,
  listConversations,
  listWorkspaces,
} from '@/api/workspace'
import { disposeChatStore } from '@/stores/chat-registry'
import type { Conversation, Workspace } from '@/types'

interface WorkspaceSessionState {
  /** 全部工作空间（侧栏空间选择器用） */
  workspaces: Workspace[]
  /** 是否已拉过一次空间列表 —— 侧栏首次挂载据此决定要不要拉 */
  workspacesLoaded: boolean
  /** 当前选中的工作空间 id —— 持久化（last-used），进 App 还原 */
  activeWorkspaceId: string | null
  /** 当前空间的会话列表（后端 updated_at 倒序，新建头插保持最近在前） */
  conversations: Conversation[]
  /** conversations 当前归属哪个空间 —— 判断是否需要为某空间重新加载 */
  convLoadedFor: string | null
  /** 正在为哪个空间加载会话（侧栏 loading 占位 + 并发去重） */
  convLoadingFor: string | null

  /** 拉空间列表 + 校正 activeWorkspaceId（无效/为空落到第一个，有效则确保会话已加载） */
  loadWorkspaces: () => Promise<void>
  /** 切到某空间：换 activeWorkspaceId + 加载其会话（id 不变则仅确保已加载） */
  setActiveWorkspace: (workspaceId: string) => void
  /** 加载某空间会话（已加载且非 force 跳过；并发去重） */
  loadConversations: (workspaceId: string, opts?: { force?: boolean }) => Promise<void>
  /** 新建会话：建成后头插当前列表，返回新会话（失败返 null；导航交调用方） */
  createConversation: (workspaceId: string) => Promise<Conversation | null>
  /** 删除会话：连带回收 chat 桶 + 从列表移除（导航交调用方） */
  deleteConversation: (workspaceId: string, conversationId: string) => Promise<void>
  /** 创建空间后头插列表（WorkspacesPage 调，保持侧栏选择器同步） */
  addWorkspace: (workspace: Workspace) => void
  /** 删除空间后从列表移除 + 必要时改选 active（WorkspacesPage 调） */
  removeWorkspace: (workspaceId: string) => void
}

export const useWorkspaceSession = create<WorkspaceSessionState>()(
  persist(
    (set, get) => ({
      workspaces: [],
      workspacesLoaded: false,
      activeWorkspaceId: null,
      conversations: [],
      convLoadedFor: null,
      convLoadingFor: null,

      loadWorkspaces: async () => {
        let workspaces: Workspace[]
        try {
          workspaces = await listWorkspaces()
        } catch {
          return // 拦截器已 toast
        }
        set({ workspaces, workspacesLoaded: true })
        // 校正当前选中：无效 / 列表为空 → 落到第一个；有效 → 确保会话已加载
        const { activeWorkspaceId } = get()
        const valid = !!activeWorkspaceId && workspaces.some((w) => w.id === activeWorkspaceId)
        if (valid) {
          get().loadConversations(activeWorkspaceId!)
        } else if (workspaces.length > 0) {
          get().setActiveWorkspace(workspaces[0].id)
        } else {
          set({ activeWorkspaceId: null, conversations: [], convLoadedFor: null })
        }
      },

      setActiveWorkspace: (workspaceId) => {
        if (get().activeWorkspaceId === workspaceId) {
          // 已是当前空间：仅确保会话已加载（首次进入 / 刷新场景）
          get().loadConversations(workspaceId)
          return
        }
        // 切空间：先清掉上个空间的列表，避免闪旧数据，再加载新空间
        set({ activeWorkspaceId: workspaceId, conversations: [], convLoadedFor: null })
        get().loadConversations(workspaceId)
      },

      loadConversations: async (workspaceId, opts) => {
        const { convLoadedFor, convLoadingFor } = get()
        if (convLoadingFor === workspaceId) return
        if (!opts?.force && convLoadedFor === workspaceId) return
        set({ convLoadingFor: workspaceId })

        let conversations: Conversation[]
        try {
          conversations = await listConversations(workspaceId)
        } catch {
          set((s) => ({
            convLoadingFor: s.convLoadingFor === workspaceId ? null : s.convLoadingFor,
          }))
          return // 拦截器已 toast
        }
        // 加载期间用户可能已切走：只在仍是当前空间时写入，否则只清 loading 标记
        if (get().activeWorkspaceId !== workspaceId) {
          set((s) => ({
            convLoadingFor: s.convLoadingFor === workspaceId ? null : s.convLoadingFor,
          }))
          return
        }
        set({ conversations, convLoadedFor: workspaceId, convLoadingFor: null })
      },

      createConversation: async (workspaceId) => {
        let created: Conversation
        try {
          created = await apiCreateConversation(workspaceId)
        } catch {
          return null // 拦截器已 toast
        }
        if (get().activeWorkspaceId === workspaceId) {
          set((s) => ({ conversations: [created, ...s.conversations] }))
        }
        return created
      },

      deleteConversation: async (workspaceId, conversationId) => {
        try {
          await apiDeleteConversation(workspaceId, conversationId)
        } catch {
          return // 删除失败不动本地状态
        }
        // 回收该对话的桶（中断在跑的流 + 释放内存）
        disposeChatStore(conversationId)
        if (get().activeWorkspaceId === workspaceId) {
          set((s) => ({
            conversations: s.conversations.filter((c) => c.id !== conversationId),
          }))
        }
      },

      addWorkspace: (workspace) =>
        set((s) => ({ workspaces: [workspace, ...s.workspaces] })),

      removeWorkspace: (workspaceId) => {
        const { workspaces, activeWorkspaceId } = get()
        const remaining = workspaces.filter((w) => w.id !== workspaceId)
        set({ workspaces: remaining })
        if (activeWorkspaceId !== workspaceId) return
        // 删的是当前空间：改选第一个剩余空间（无则置空）
        const next = remaining[0]?.id ?? null
        set({ activeWorkspaceId: next, conversations: [], convLoadedFor: null })
        if (next) get().loadConversations(next)
      },
    }),
    {
      name: 'workspace-session',
      // 只持久化 last-used 空间；列表 / 会话每次进 App 重新拉
      partialize: (s) => ({ activeWorkspaceId: s.activeWorkspaceId }),
    },
  ),
)
