/**
 * Workspace 本地 mock store（v0：纯内存，刷新还原初始 mockWorkspaces）
 *
 * 列表页 / 详情页共用。v1 切后端时整个换成 fetch hook，组件不动。
 */

import { create } from 'zustand'
import type { Conversation, Workspace } from '@/types'
import { mockWorkspaces } from './mock'

interface WorkspaceMockState {
  workspaces: Workspace[]
  add: (ws: Workspace) => void
  update: (id: string, patch: Partial<Workspace>) => void
  remove: (id: string) => void
  getById: (id: string) => Workspace | undefined
  /** 给某空间新建一个 conversation，push 到 conversations 头部 */
  addConversation: (workspaceId: string, conv: Conversation) => void
}

export const useWorkspaceMockStore = create<WorkspaceMockState>((set, get) => ({
  workspaces: [...mockWorkspaces],

  add: (ws) => set((s) => ({ workspaces: [ws, ...s.workspaces] })),

  update: (id, patch) =>
    set((s) => ({
      workspaces: s.workspaces.map((w) =>
        w.id === id ? { ...w, ...patch, updated_at: new Date().toISOString() } : w,
      ),
    })),

  remove: (id) => set((s) => ({ workspaces: s.workspaces.filter((w) => w.id !== id) })),

  getById: (id) => get().workspaces.find((w) => w.id === id),

  addConversation: (workspaceId, conv) =>
    set((s) => ({
      workspaces: s.workspaces.map((w) =>
        w.id === workspaceId
          ? { ...w, conversations: [conv, ...w.conversations], updated_at: new Date().toISOString() }
          : w,
      ),
    })),
}))
