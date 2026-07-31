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
  generateConversationTitle,
  listConversations,
  listWorkspaces,
} from '@/api/workspace'
import { disposeChatStore } from '@/stores/chat-registry'
import type { Conversation, Workspace } from '@/types'

/** 占位标题取用户那句话的前几个字 —— 只为填满起名那 1~2 秒的空窗 */
const TITLE_PLACEHOLDER_CHARS = 10

/**
 * 正在起名的对话 id —— 并发闸，不进 store。
 *
 * 不用 titlePlaceholders 兼任这个闸：起名失败时占位要**留着**（比「新对话」好看，
 * 且刷新即消失、不骗人），但失败后又必须允许下次重试 —— 两个诉求打架，拆成两份状态。
 * 放模块级而非 store：它不参与渲染，进 store 只会白白触发订阅者重渲染。
 */
const titleInFlight = new Set<string>()

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
  /**
   * conversationId → 临时占位标题（用户那句话的前几个字）。
   *
   * **绝不能写进 `conversations[].title`**：那个字段必须永远等于库里那份，
   * 「title 为空 = 还没起过名」是触发起名的唯一判据，掺进自己编的占位就废了。
   * 渲染时才叠上去（走 useConversationTitle）。
   */
  titlePlaceholders: Record<string, string>

  /** 拉空间列表 + 校正 activeWorkspaceId（无效/为空落到第一个，有效则确保会话已加载） */
  loadWorkspaces: () => Promise<void>
  /** 切到某空间：换 activeWorkspaceId + 加载其会话（id 不变则仅确保已加载） */
  setActiveWorkspace: (workspaceId: string) => void
  /** 加载某空间会话（已加载且非 force 跳过；并发去重） */
  loadConversations: (workspaceId: string, opts?: { force?: boolean }) => Promise<void>
  /** 没名字就去起一个（发消息时 / 进对话时各触发一次，内部自己去重） */
  ensureConversationTitle: (
    workspaceId: string,
    conversationId: string,
    sourceText: string,
  ) => Promise<void>
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
      titlePlaceholders: {},

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

      ensureConversationTitle: async (workspaceId, conversationId, sourceText) => {
        // 库里已有名字（系统起的 / 用户改的）→ 不碰
        if (get().conversations.find((c) => c.id === conversationId)?.title) return
        if (titleInFlight.has(conversationId)) return

        const text = sourceText.trim()
        if (!text) return

        titleInFlight.add(conversationId)
        // 先亮占位补上这 1~2 秒的空窗，请求再发
        set((s) => ({
          titlePlaceholders: {
            ...s.titlePlaceholders,
            [conversationId]: text.slice(0, TITLE_PLACEHOLDER_CHARS),
          },
        }))

        let title: string
        try {
          ;({ title } = await generateConversationTitle(workspaceId, conversationId, text))
        } catch {
          // 静默（api 层已 silent）—— 库里仍是空，下次进对话会再试一次。
          // 占位留着不撤：撤了这条会当场跳回「新对话」，而它并没有更真实
          return
        } finally {
          titleInFlight.delete(conversationId)
        }

        // 真标题到手：写进列表，同时撤掉占位（它的使命结束，留着会盖住重命名）
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === conversationId ? { ...c, title } : c,
          ),
          titlePlaceholders: Object.fromEntries(
            Object.entries(s.titlePlaceholders).filter(([id]) => id !== conversationId),
          ),
        }))
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
        titleInFlight.delete(conversationId)
        if (get().activeWorkspaceId === workspaceId) {
          set((s) => ({
            conversations: s.conversations.filter((c) => c.id !== conversationId),
            titlePlaceholders: Object.fromEntries(
              Object.entries(s.titlePlaceholders).filter(([id]) => id !== conversationId),
            ),
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

/**
 * 拿一个「算显示标题」的函数 —— `真标题 → 占位 → 新对话` 三级回落。
 *
 * 做成「一次订阅 + 返回纯函数」而不是 `useConversationTitle(conv)`：会话列表要在
 * map 里逐条算标题，逐条调 hook 违反 hooks 规则。同文件的 statuses 也是这个用法。
 */
export function useConversationTitle() {
  const placeholders = useWorkspaceSession((s) => s.titlePlaceholders)
  return (conv: Pick<Conversation, 'id' | 'title'>) =>
    conv.title || placeholders[conv.id] || '新对话'
}
