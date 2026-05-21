/**
 * User 业务类型 — 对齐 backend/app/schemas/user_schema.py
 *
 * 前端 UUID / datetime / EmailStr 都用 string，运行时不做严格校验，依赖后端。
 * 表单校验（如 username 3-20 字符、password 长度等）在 views 层用 zod / 手写规则做。
 */

/** 用户对外公开信息（GET /me 返回的 user 字段） */
export interface User {
  id: string
  username: string
  email: string
  nick_name: string
  avatar_url: string
  is_active: boolean
  is_admin: boolean
  /** ISO 8601 datetime string */
  created_at: string
  /** ISO 8601 datetime string */
  updated_at: string
}

/** 注册请求体 */
export interface UserRegisterPayload {
  /** 字母 / 数字 / 下划线，3-20 字符 */
  username: string
  email: string
  /** 6-64 字符 */
  password: string
  /** 昵称，2-50 字符，必填 */
  nick_name: string
}

/** 登录请求体 */
export interface UserLoginPayload {
  username: string
  password: string
}

/** 登录成功响应：token + 当前用户信息 */
export interface TokenPayload {
  access_token: string
  token_type: 'bearer'
  user: User
}
