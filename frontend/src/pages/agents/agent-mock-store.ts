/**
 * Agent 本地 mock store（v0 切片：纯内存，刷新还原初始 mockAgents）
 *
 * 列表页 / 详情页共用这一份状态，保证创建后跳详情能拿到、配置改动即时反映回列表。
 * v1 切到后端时，整个 store 换成 fetch hook，组件不动。
 */

import { create } from 'zustand'
import type { Agent } from '@/types'
import { mockAgents } from './mock'

interface AgentMockState {
  agents: Agent[]
  add: (agent: Agent) => void
  /** 部分更新某个 agent，自动刷新 updated_at */
  update: (id: string, patch: Partial<Agent>) => void
  remove: (id: string) => void
  /** 详情页便利：按 id 取，找不到返回 undefined */
  getById: (id: string) => Agent | undefined
}

export const useAgentMockStore = create<AgentMockState>((set, get) => ({
  agents: [...mockAgents],

  add: (agent) => set((s) => ({ agents: [agent, ...s.agents] })),

  update: (id, patch) =>
    set((s) => ({
      agents: s.agents.map((a) =>
        a.id === id ? { ...a, ...patch, updated_at: new Date().toISOString() } : a,
      ),
    })),

  remove: (id) => set((s) => ({ agents: s.agents.filter((a) => a.id !== id) })),

  getById: (id) => get().agents.find((a) => a.id === id),
}))
