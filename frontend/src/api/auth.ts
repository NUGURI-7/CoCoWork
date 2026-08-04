/**
 * Auth API — 对接 backend/app/api/routes/user/user.py
 *
 * 路径前缀 `/users`，加上 axios baseURL `/api/v1`，实际命中：
 *   POST  /api/v1/users/register
 *   POST  /api/v1/users/login
 *   GET   /api/v1/users/me
 *   GET   /api/v1/users              （管理员）
 *   PATCH /api/v1/users/{id}/status  （管理员）
 */

import { get, patch, post } from '@/request'
import type {
  TokenPayload,
  User,
  UserLoginPayload,
  UserRegisterPayload,
  UserStatusPayload,
} from '@/types'

/**
 * 注册新用户。
 *
 * 后端约定：注册接口只返回 User，不签发 token。
 * 注册成功后由调用方手动跳 /login 让用户输入密码登录。
 *
 * 错误（用户名/邮箱重复等）走 silent，由表单层处理。
 */
export function register(payload: UserRegisterPayload) {
  return post<User>('/users/register', payload, { silent: true })
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

/**
 * 列出全部用户（仅管理员）。
 *
 * 后端不分页，一次返全量 —— 搜索与角色筛选都在页面里本地做，输入即时响应，
 * 不为个位数用户加防抖请求。后端那两个查询参数留着，等真需要分页时才用得上。
 */
export function listUsers() {
  return get<User[]>('/users')
}

/**
 * 启用 / 停用某个账户（仅管理员）。
 *
 * 停用是即时生效的：后端每个请求都拿 token 里的 id 回查一次真人并校 is_active，
 * 所以对方手里已签发的 token 会在下一次请求就失效，不用等它过期。
 */
export function setUserStatus(userId: string, isActive: boolean) {
  return patch<User>(`/users/${userId}/status`, {
    is_active: isActive,
  } satisfies UserStatusPayload)
}
