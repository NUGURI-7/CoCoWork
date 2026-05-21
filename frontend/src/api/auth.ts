/**
 * Auth API — 对接 backend/app/api/routes/user.py
 *
 * 路径前缀 `/users`，加上 axios baseURL `/api/v1`，实际命中：
 *   POST /api/v1/users/register
 *   POST /api/v1/users/login
 *   GET  /api/v1/users/me
 */

import { get, post } from '@/request'
import type { TokenPayload, User, UserLoginPayload, UserRegisterPayload } from '@/types'

/**
 * 注册新用户。
 * 错误（用户名/邮箱重复等）走 silent，由表单层处理。
 */
export function register(payload: UserRegisterPayload) {
  return post<TokenPayload>('/users/register', payload, { silent: true })
}

/**
 * 用户名 + 密码登录。
 * 错误（用户名密码错等）走 silent，由表单层处理。
 */
export function login(payload: UserLoginPayload) {
  return post<TokenPayload>('/users/login', payload, { silent: true })
}

/**
 * 获取当前登录用户信息。
 * 默认轨：401 拦截器自动清 token + 跳 /login。
 */
export function fetchMe() {
  return get<User>('/users/me')
}
