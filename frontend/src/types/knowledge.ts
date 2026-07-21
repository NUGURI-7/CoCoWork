/**
 * 知识库模块类型 — 对齐 backend/app/schemas/knowledge/knowledge_base_schema.py
 */

/** 库级状态（spec §3.1：换模型 reindexing） */
export type KnowledgeBaseStatus = 'ready' | 'reindexing'

/** 检索模式（对齐 backend RetrievalMode StrEnum） */
export type RetrievalMode = 'vector' | 'keyword' | 'hybrid'

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
  retrieval_mode: RetrievalMode
  rerank_model_id: string | null
  rerank_model_name: string | null
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
  retrieval_mode?: RetrievalMode
  /** null = 关闭精排；不传 = 不变 */
  rerank_model_id?: string | null
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

// ============================================================================
// 检索 / 命中测试
// ============================================================================

/** 单条命中结果（对齐后端 RetrievalHit）
 *
 * - `content`：命中后返回的整段（父子块的父级）
 * - `chunk_text`：实际命中的子块原文，调试切块时看
 * - `score`：相似度 0~1（= 1 - 余弦距离），越大越相关
 */
export interface RetrievalHit {
  paragraph_id: string
  document_id: string
  doc_name: string
  content: string
  chunk_text: string
  score: number
}

/** 命中测试响应（对齐后端 RetrievalTestOut）：命中列表 + 四段耗时（毫秒）
 *
 * - `embed_ms`：query 向量化耗时（调 embedding 模型，通常占大头）
 * - `search_ms`：检索 SQL 耗时
 * - `rerank_ms`：精排耗时（未开启精排时为 0）
 * - `total_ms`：总耗时
 */
export interface RetrievalTestResult {
  hits: RetrievalHit[]
  embed_ms: number
  search_ms: number
  rerank_ms: number
  total_ms: number
}

// ============================================================================
// Document — 批量操作
// ============================================================================

/** 批量向量化结果（对齐后端 BatchProcessOut）
 *
 * - `triggered`：已入队处理的文档 id（前端乐观标 processing + 轮询）
 * - `skipped`：状态不允许、被跳过的文档 id（前端提示用户）
 */
export interface BatchProcessResult {
  triggered: string[]
  skipped: string[]
}
