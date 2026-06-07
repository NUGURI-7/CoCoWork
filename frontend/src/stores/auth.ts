/**
 * Auth Store — 全局认证状态。
 *
 * 持久化策略：
 *  - `token` 写 localStorage（与 request 拦截器从 localStorage 读 token 对齐）
 *  - `user` 不持久化：刷新后 token 还在但 user=null，router beforeLoad 调 `fetchMe()`
 *    保证 is_active / is_admin / nick_name 等始终是服务端最新值
 *
 * Token 过期处理：
 *  - JWT body 含 `exp` 字段（Unix 秒），登录后 / 启动时按剩余时间排 setTimeout
 *  - 到点自动 logout + 跳转 /login（带 redirect 回到当前路径）
 *  - beforeLoad 顺手 `isExpired()` 兜底（防系统休眠睡过头 / 改了系统时间）
 *  - 后端 401 仍由 request 拦截器兜底处理（双保险）
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

let expiryTimer: ReturnType<typeof setTimeout> | null = null

/**
 * 从 JWT 取 exp（Unix 秒）。JWT body 是 base64url 编码 JSON，第二段。
 * 任何解析错误返回 null —— 解不出来不主动登出，让后端 401 兜底。
 */
function decodeJwtExp(token: string): number | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    // base64url → base64（JWT 用 url-safe 编码，- _ 替换 + /）
    const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(atob(padded)) as { exp?: number }
    return typeof payload.exp === 'number' ? payload.exp : null
  } catch {
    return null
  }
}

function clearAutoLogoutTimer() {
  if (expiryTimer) {
    clearTimeout(expiryTimer)
    expiryTimer = null
  }
}

/**
 * 按 token 的 exp 排 setTimeout，到点触发自动登出。
 * 已过期 → 立刻触发；解不出 exp → 不排定时器（让后端 401 兜底）。
 */
function scheduleAutoLogout(token: string) {
  clearAutoLogoutTimer()
  const exp = decodeJwtExp(token)
  if (exp === null) return
  const msLeft = exp * 1000 - Date.now()
  if (msLeft <= 0) {
    triggerAutoLogout()
    return
  }
  expiryTimer = setTimeout(triggerAutoLogout, msLeft)
}

/**
 * 触发自动登出 —— 清状态 + 跳登录页（保留当前路径作 redirect 回跳目标）。
 * 已在 /login 则不跳（防循环）。
 */
function triggerAutoLogout() {
  useAuthStore.getState().logout()
  if (window.location.pathname.startsWith('/login')) return
  const redirect = window.location.pathname + window.location.search
  window.location.href = `/login?redirect=${encodeURIComponent(redirect)}`
}

interface AuthState {
  // ---- state ----
  token: string | null
  user: User | null

  // ---- getters (Zustand 用函数代替 Pinia computed) ----
  isLoggedIn: () => boolean
  isAdmin: () => boolean
  /** token 是否已过期（JWT exp 校验，解不出返回 false 不主动拦截）。 */
  isExpired: () => boolean

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
  isExpired: () => {
    const t = get().token
    if (!t) return true
    const exp = decodeJwtExp(t)
    if (exp === null) return false
    return Date.now() / 1000 >= exp
  },

  // ------------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------------
  login: async (payload) => {
    const data = await authApi.login(payload)
    localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    set({ token: data.access_token, user: data.user })
    scheduleAutoLogout(data.access_token)
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
    clearAutoLogoutTimer()
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    set({ token: null, user: null })
  },
}))

// 模块初始化：若 localStorage 已有 token（刷新场景），按 exp 排定时器。
{
  const initialToken = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (initialToken) scheduleAutoLogout(initialToken)
}
