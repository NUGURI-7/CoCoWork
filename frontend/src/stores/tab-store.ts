/**
 * 通用标签页状态工厂
 *
 * 前台（工作台）和后台（admin）各调一次 createTabStore 生成独立实例，
 * 共享同一套逻辑，只是首页标签不同。
 */

import { LayoutDashboard, type LucideIcon } from 'lucide-react'
import { create, type StoreApi, type UseBoundStore } from 'zustand'

export interface Tab {
  /** 路由路径，作为唯一标识 */
  path: string
  /** 显示标题 */
  title: string
  /** 标签图标（可选） */
  icon?: LucideIcon
  /** 是否固定（不可关闭） */
  pinned?: boolean
}

export interface TabsState {
  tabs: Tab[]
  activePath: string

  open: (tab: Omit<Tab, 'pinned'>) => void
  activate: (path: string) => void
  close: (path: string) => void
  closeOthers: () => void
  closeAll: () => void
}

export function createTabStore(homeTab: Tab): UseBoundStore<StoreApi<TabsState>> {
  const pinnedHome: Tab = { ...homeTab, pinned: true }

  return create<TabsState>((set, get) => ({
    tabs: [pinnedHome],
    activePath: pinnedHome.path,

    open: (tab) => {
      const { tabs } = get()
      const exists = tabs.find((t) => t.path === tab.path)
      if (exists) {
        set({ activePath: tab.path })
      } else {
        set({ tabs: [...tabs, { ...tab }], activePath: tab.path })
      }
    },

    activate: (path) => {
      set({ activePath: path })
    },

    close: (path) => {
      const { tabs, activePath } = get()
      const target = tabs.find((t) => t.path === path)
      if (!target || target.pinned) return

      const newTabs = tabs.filter((t) => t.path !== path)
      if (activePath === path) {
        const closedIdx = tabs.findIndex((t) => t.path === path)
        const nextActive = newTabs[Math.min(closedIdx, newTabs.length - 1)]
        set({ tabs: newTabs, activePath: nextActive.path })
      } else {
        set({ tabs: newTabs })
      }
    },

    closeOthers: () => {
      const { tabs, activePath } = get()
      set({ tabs: tabs.filter((t) => t.pinned || t.path === activePath) })
    },

    closeAll: () => {
      set({ tabs: [pinnedHome], activePath: pinnedHome.path })
    },
  }))
}

/** 工作台标签 */
export const useWorkspaceTabsStore = createTabStore({ path: '/', title: '主页', icon: LayoutDashboard })

/** Admin 标签 */
export const useAdminTabsStore = createTabStore({ path: '/admin', title: '概览', icon: LayoutDashboard })
