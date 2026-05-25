/**
 * 知识库模块类型 — 对齐 backend/app/schemas/knowledge/knowledge_base_schema.py
 */

/** 库级状态（spec §3.1：换模型 reindexing） */
export type KnowledgeBaseStatus = 'ready' | 'reindexing'

/** 库级切块配置（一套，作用于库内所有文档） */
export interface ChunkConfig {
  chunk_size: number
  overlap: number
  strategy: 'recursive'
}

/** KnowledgeBase 实例（GET 返回） */
export interface KnowledgeBase {
  id: string
  name: string
  description: string
  embedding_model_id: string
  embedding_model_name: string
  embedding_dim: number
  chunk_config: ChunkConfig
  status: KnowledgeBaseStatus
  doc_count: number
  chunk_count: number
  created_at: string
  updated_at: string
}

/** 创建知识库请求体。embedding_dim 由后端随模型锁定，不在此处传。 */
export interface KnowledgeBaseCreatePayload {
  name: string
  description?: string
  embedding_model_id: string
  chunk_config?: Partial<ChunkConfig>
}

/** 更新知识库请求体（部分更新）。不可改 embedding 模型——后端 schema 已锁。 */
export interface KnowledgeBaseUpdatePayload {
  name?: string
  description?: string
  chunk_config?: ChunkConfig
}
