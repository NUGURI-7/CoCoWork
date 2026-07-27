/**
 * Skill API — 对接 backend/app/api/routes/skill/*
 *
 * 路径前缀 `/skills`，加上 axios baseURL `/api/v1`。
 */

import { get } from '@/request'
import type { Skill } from '@/types'

/** 列出当前可挂载的 skill（内置；未来含用户上传的）。 */
export function listSkills() {
  return get<Skill[]>('/skills')
}
