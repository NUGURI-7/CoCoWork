/**
 * Skill API — 对接 backend/app/api/routes/skill/*
 *
 * 路径前缀 `/skills`，加上 axios baseURL `/api/v1`。
 */

import { del, get, post } from '@/request'
import type { Skill } from '@/types'

/** 列出当前可挂载的 skill（内置 + 自己上传的，合并成一份）。 */
export function listSkills() {
  return get<Skill[]>('/skills')
}

/**
 * 上传一个 skill 包（zip）。
 *
 * name / description 由后端从包里的 SKILL.md 读出，前端不填也填不了。
 */
export function uploadSkill(file: File) {
  const data = new FormData()
  data.append('file', file)
  return post<Skill>('/skills', data)
}

/** 删除自己上传的 skill（内置的没有 id，删不了）。 */
export function deleteSkill(id: string) {
  return del<null>(`/skills/${id}`)
}
