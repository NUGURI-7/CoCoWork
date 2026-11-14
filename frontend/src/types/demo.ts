/**
 * 官网免登录体验 — 对齐 backend/app/schemas/demo/demo_schema.py
 */

/** 体验场景该跳去哪：单 Agent 给 Agent id，工作空间给访客自己那份的 id */
export interface SceneEntry {
  kind: 'agent' | 'workspace'
  target_id: string
}

/** 当前用户在这个场景今天还能发几条；正式用户不受限，两个字段都为 null */
export interface SceneQuota {
  remaining: number | null
  limit: number | null
}
