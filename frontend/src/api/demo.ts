/**
 * 官网免登录体验 API — 对接 backend/app/api/routes/demo/demo.py
 *
 *   POST /api/v1/demo/guest-session          建临时账号并签发凭证
 *   GET  /api/v1/demo/scenes/{scene}/entry   场景名 → 目标页面
 *
 * 两个都走 silent：错误由 /try 页面自己展示成整页说明，不弹 toast。
 */
import { get, post } from '@/request'
import type { SceneEntry, TokenPayload } from '@/types'

export function createGuestSession() {
  return post<TokenPayload>('/demo/guest-session', undefined, { silent: true })
}

export function getSceneEntry(scene: string) {
  return get<SceneEntry>(`/demo/scenes/${encodeURIComponent(scene)}/entry`, undefined, {
    silent: true,
  })
}
