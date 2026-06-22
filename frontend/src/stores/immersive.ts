/**
 * 沉浸模式开关 —— 每个工作空间各自记忆。
 *
 * 开 = 隐藏 App 自身所有 chrome（顶栏 / TabBar / 面包屑 / 左右侧栏），会话铺满，
 * 像普通对话 Agent UI。仍在浏览器普通标签页内，不接管浏览器全屏。
 *
 * 两层状态：
 * - prefs：每空间偏好（workspaceId → bool），持久化到 localStorage，下次进同一
 *   空间还原上次的样子。
 * - active：当前生效值，AppShell + 页面都读它决定布局。**不持久化** —— 进某空间
 *   时由 enter() 从 prefs 同步，离开页面 leave() 复位 false，否则别的页面会顶着
 *   一个没有顶栏的空壳。
 *
 * 时序：页面用 useLayoutEffect 调 enter/leave —— 在 paint 前同步 active，避免进
 * 一个「上次沉浸」的空间时先闪一下 chrome。
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ImmersiveState {
  /** 当前生效值；AppShell + 页面读它 */
  active: boolean
  /** 每空间偏好，持久化 */
  prefs: Record<string, boolean>
  /** 进入某空间：active ← 该空间偏好 */
  enter: (workspaceId: string) => void
  /** 离开页面：active 复位（不动 prefs） */
  leave: () => void
  /** 切换某空间：写 prefs + 同步 active */
  set: (workspaceId: string, v: boolean) => void
  /** 会话面板开/关，每空间记忆（沉浸左栏用），刷新还原 */
  convOpen: Record<string, boolean>
  /** 设某空间的会话面板开/关 */
  setConvOpen: (workspaceId: string, v: boolean) => void
}

export const useImmersiveStore = create<ImmersiveState>()(
  persist(
    (set, get) => ({
      active: false,
      prefs: {},
      enter: (workspaceId) => set({ active: get().prefs[workspaceId] ?? false }),
      leave: () => set({ active: false }),
      set: (workspaceId, v) =>
        set((s) => ({ active: v, prefs: { ...s.prefs, [workspaceId]: v } })),
      convOpen: {},
      setConvOpen: (workspaceId, v) =>
        set((s) => ({ convOpen: { ...s.convOpen, [workspaceId]: v } })),
    }),
    {
      name: 'immersive',
      // 持久化 prefs + convOpen；active 是临时态，进页面时重新同步
      partialize: (s) => ({ prefs: s.prefs, convOpen: s.convOpen }),
    },
  ),
)
