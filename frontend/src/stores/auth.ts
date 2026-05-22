/**
 * Auth Store — 全局认证状态。
 *
 * 持久化策略：
 *  - `token` 写 localStorage（与 request 拦截器从 localStorage 读 token 对齐）
 *  - `user` 不持久化：刷新后 token 还在但 user=null，router beforeLoad 调 `fetchMe()`
 *    保证 is_active / is_admin / nick_name 等始终是服务端最新值
 *
 * 用法：
 *   const auth = useAuthStore()
 *   await useAuthStore.getState().login({ username, password })
 *   if (useAuthStore.getState().isLoggedIn()) ...
 */

import { create } from 'zustand'
import * as authApi from '@/api/auth'
import type { User, UserLoginPayload } from '@/types'

const TOKEN_STORAGE_KEY = 'token'

interface AuthState {
  // ---- state ----
  token: string | null
  user: User | null

  // ---- getters (Zustand 用函数代替 Pinia computed) ----
  isLoggedIn: () => boolean
  isAdmin: () => boolean

  // ---- actions ----
  // 注：注册不进 store —— 后端注册接口不签发 token，由 Register 页面直接调 authApi.register
  // 后跳 /login 走正式登录建立会话。
  login: (payload: UserLoginPayload) => Promise<User>
  fetchMe: () => Promise<User>
  logout: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // ------------------------------------------------------------------------
  // State — 初始 token 从 localStorage 读，与拦截器对齐
  // ------------------------------------------------------------------------
  token: localStorage.getItem(TOKEN_STORAGE_KEY),
  user: null,

  // ------------------------------------------------------------------------
  // Getters
  // ------------------------------------------------------------------------
  isLoggedIn: () => !!get().token,
  isAdmin: () => get().user?.is_admin === true,

  // ------------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------------
  login: async (payload) => {
    const data = await authApi.login(payload)
    localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    set({ token: data.access_token, user: data.user })
    return data.user
  },

  /**
   * 拉取当前用户。
   * 用于刷新后 token 还在但 user=null 的场景（router beforeLoad 调用）。
   * 401 时 request 拦截器会清 token 跳 /login，这里只负责赋值 user。
   */
  fetchMe: async () => {
    const u = await authApi.fetchMe()
    set({ user: u })
    return u
  },

  logout: () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    set({ token: null, user: null })
  },
}))
