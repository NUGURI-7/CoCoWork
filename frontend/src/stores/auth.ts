/**
 * Auth Store — 全局认证状态。
 *
 * 持久化策略：
 *  - `token` 写 localStorage（与 request 拦截器从 localStorage 读 token 对齐）
 *  - `user` 不持久化：刷新后 token 还在但 user=null，router 守卫层调 `fetchMe()`
 *    保证 is_active / is_admin / nick_name 等始终是服务端最新值
 *
 * 用法：
 *   const auth = useAuthStore()
 *   await auth.login({ username, password })
 *   if (auth.isLoggedIn) ...
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import type { User, UserLoginPayload, UserRegisterPayload } from '@/types'

const TOKEN_STORAGE_KEY = 'token'

export const useAuthStore = defineStore('auth', () => {
  // ------------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------------
  const token = ref<string | null>(localStorage.getItem(TOKEN_STORAGE_KEY))
  const user = ref<User | null>(null)

  // ------------------------------------------------------------------------
  // Getters
  // ------------------------------------------------------------------------
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin === true)

  // ------------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------------
  function setSession(payload: { access_token: string; user: User }) {
    token.value = payload.access_token
    user.value = payload.user
    localStorage.setItem(TOKEN_STORAGE_KEY, payload.access_token)
  }

  async function login(payload: UserLoginPayload) {
    const data = await authApi.login(payload)
    setSession(data)
    return data.user
  }

  async function register(payload: UserRegisterPayload) {
    const data = await authApi.register(payload)
    setSession(data)
    return data.user
  }

  /**
   * 拉取当前用户。
   * 用于刷新后 token 还在但 user=null 的场景（router 守卫调用）。
   * 401 时 request 拦截器会清 token 跳 /login，这里只负责赋值 user。
   */
  async function fetchMe() {
    const u = await authApi.fetchMe()
    user.value = u
    return u
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }

  return {
    // state
    token,
    user,
    // getters
    isLoggedIn,
    isAdmin,
    // actions
    login,
    register,
    fetchMe,
    logout,
  }
})
