import { create } from 'zustand'

/** 单个对话的实时状态 —— idle 空闲 / running 在跑 / error 上一轮出错 */
export type ConversationStatus = 'idle' | 'running' | 'error'

interface StreamStatusState {
  /** conversationId → 状态。无条目 = 没开过本对话，按 idle 处理 */
  statuses: Record<string, ConversationStatus>
  set: (conversationId: string, status: ConversationStatus) => void
  clear: () => void
}

/**
 * 对话流实时状态表。
 *
 * 由 chat-registry 在「桶创建时」订阅每个 chat store 写入，更新与 React 组件挂载
 * 无关 —— 后台在跑的对话（其 WorkspaceChat 已卸载）照样能更新状态。
 * ConversationSwitcher 读它给每条对话画状态点，实现「同时盯多个 thread」。
 */
export const useStreamStatusStore = create<StreamStatusState>((set) => ({
  statuses: {},
  set: (conversationId, status) =>
    set((s) => ({ statuses: { ...s.statuses, [conversationId]: status } })),
  clear: () => set({ statuses: {} }),
}))
