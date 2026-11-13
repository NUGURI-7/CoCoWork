/**
 * 侧栏会话区的模式：工作空间 / 单个 Agent。持久化，刷新后保持上次的选择。
 * 进入对应页面时由侧栏跟随网址自动切换，手动切换走侧栏上的切换按钮。
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type SidebarMode = 'workspace' | 'agent'

interface SidebarModeState {
  mode: SidebarMode
  setMode: (mode: SidebarMode) => void
}

export const useSidebarMode = create<SidebarModeState>()(
  persist(
    (set) => ({
      mode: 'workspace',
      setMode: (mode) => set({ mode }),
    }),
    { name: 'sidebar-mode' },
  ),
)
