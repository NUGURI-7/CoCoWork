/**
 * 路由 → tab 自动同步
 *
 * 调用方只管 navigate，tab 由路由变化自动驱动，避免「跳转和 tab 不一致」。
 * - useTabSync(store)：挂在 Shell 顶层，监听 router location 变化，按当前匹配路由的
 *   staticData.tabTitle / tabIcon 自动 openTab；没有 staticData 的路由跳过（如 login）
 * - useTabTitle(path, title)：详情页用，把路由 fallback 名（如 "Agent"）覆盖成真名
 *   （如 "代码研究员"）。path 由调用方从 useParams 派生传入。
 */

import { useEffect } from 'react'
import { useRouter } from '@tanstack/react-router'
import type { LucideIcon } from 'lucide-react'
import type { StoreApi, UseBoundStore } from 'zustand'

import { useAdminTabsStore, useWorkspaceTabsStore, type TabsState } from './tab-store'

interface TabStaticData {
  tabTitle?: string
  tabIcon?: LucideIcon
}

/**
 * 挂在 Shell 顶层一次即可（AppShell / AdminShell 各调一次）
 *
 * 用 router.subscribe('onResolved') 监听 navigation 完成事件，此时 pathname 和 matches
 * 都已 resolved，不会出现 selector 在不同 render 拿到错位组合的中间态。
 */
export function useTabSync(useStore: UseBoundStore<StoreApi<TabsState>>): void {
  const router = useRouter()

  useEffect(() => {
    const sync = () => {
      const matches = router.state.matches
      const last = matches[matches.length - 1]
      const data = last?.staticData as TabStaticData | undefined
      const pathname = router.state.location.pathname
      const state = useStore.getState()
      if (data?.tabTitle) {
        state.open({ path: pathname, title: data.tabTitle, icon: data.tabIcon })
      } else {
        // 无 staticData 的路由（login / 404）仍同步 activePath，避免 sidebar 与 tab 高亮分歧
        state.activate(pathname)
      }
    }
    // mount 时立即同步一次初始路由
    sync()
    return router.subscribe('onResolved', sync)
  }, [router, useStore])
}

/**
 * 详情页用：把 path 对应 tab 的 title 覆盖成真名。title 为 undefined 时跳过（加载中）。
 *
 * - `path` 由调用方从 useParams 派生（如 `/agents/${agentId}`），跟随 params 变化——
 *   同路由 params 切换（A→B 复用组件不 remount）时也能改对各自的 tab，不会串台。
 * - 订阅「该 path 的 tab 是否已存在」：useTabSync 的 open 先建好 tab（fallback 名），
 *   tab 出现后本 effect 再覆盖真名，避免「effect 早于 open」的时序竞争。
 */
export function useTabTitle(path: string, title: string | undefined): void {
  const isAdmin = path.startsWith('/admin')
  const wsHasTab = useWorkspaceTabsStore((s) => s.tabs.some((t) => t.path === path))
  const adminHasTab = useAdminTabsStore((s) => s.tabs.some((t) => t.path === path))
  const hasTab = isAdmin ? adminHasTab : wsHasTab

  useEffect(() => {
    if (!title || !hasTab) return
    const store = isAdmin ? useAdminTabsStore : useWorkspaceTabsStore
    store.getState().setTitle(path, title)
  }, [path, title, hasTab, isAdmin])
}
