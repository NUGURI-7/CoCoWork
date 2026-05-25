/**
 * 知识库 API — 对接 backend/app/api/routes/knowledge/knowledge_base.py
 *
 * 路径前缀 `/knowledge-bases`，加上 axios baseURL `/api/v1`。
 */

import { del, get, post, put } from '@/request'
import type {
  KnowledgeBase,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseUpdatePayload,
} from '@/types'

/** 列出当前用户的知识库。 */
export function listKnowledgeBases() {
  return get<KnowledgeBase[]>('/knowledge-bases')
}

/** 获取单个知识库详情。 */
export function getKnowledgeBase(id: string) {
  return get<KnowledgeBase>(`/knowledge-bases/${id}`)
}

/**
 * 创建知识库。走 silent 由表单层 toast。
 */
export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return post<KnowledgeBase>('/knowledge-bases', payload, { silent: true })
}

/**
 * 更新知识库（部分更新；不可改 embedding 模型）。走 silent 由表单层 toast。
 */
export function updateKnowledgeBase(id: string, payload: KnowledgeBaseUpdatePayload) {
  return put<KnowledgeBase>(`/knowledge-bases/${id}`, payload, { silent: true })
}

/** 删除知识库。失败走默认拦截器 toast（与 model 模块删除约定一致）。 */
export function deleteKnowledgeBase(id: string) {
  return del<null>(`/knowledge-bases/${id}`)
}
