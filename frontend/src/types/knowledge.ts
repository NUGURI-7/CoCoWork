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

// ============================================================================
// Document
// ============================================================================

/** 文档大状态（对齐后端 Document.status） */
export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

/** 文档细分阶段（对齐后端 Document.stage）
 *
 * - `''` = init 后还没传完
 * - `'uploaded'` = 字节已传完、等向量化
 * - `'parsing'` / `'splitting'` / `'embedding'` = 向量化管线进行中（片5）
 */
export type DocumentStage = '' | 'uploaded' | 'parsing' | 'splitting' | 'embedding'

/** Document 对外形态（对齐后端 DocumentOut） */
export interface Document {
  id: string
  knowledge_base_id: string
  name: string
  file_type: string
  size: number
  char_length: number
  paragraph_count: number
  chunk_count: number
  status: DocumentStatus
  stage: DocumentStage
  error_message: string
  created_at: string
  updated_at: string
}

/** 上传策略（init 返回的判别字段） */
export type UploadStrategy = 'presign' | 'passthrough'

/** init 上传响应（对齐后端 UploadInitOut）
 *
 * - `presign` 时：用 `upload_url` + `headers` 直接 PUT 到 R2
 * - `passthrough` 时：用 `upload_endpoint` multipart POST 给后端
 */
export interface UploadInitOut {
  strategy: UploadStrategy
  document_id: string
  upload_url?: string
  upload_endpoint?: string
  headers: Record<string, string>
}
