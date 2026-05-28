/** 知识库前端 mock。
 *
 * 知识库本身已接入后端 API（types/knowledge.ts + api/knowledge.ts），此处不再 mock。
 * 文档接口尚未就绪，文档列表暂时保留 mock。
 */

import type { KnowledgeBaseStatus } from '@/types'

// ============================================================================
// 文档（mock，等后端文档接口接入后切换）
// ============================================================================

export type DocType = 'pdf' | 'md' | 'docx' | 'txt'

/** 文档状态，对齐后端 backend/app/models/knowledge.py Document.status */
export type DocStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface KnowledgeDoc {
  id: string
  kb_id: string
  name: string
  type: DocType
  size: string // 展示用，如 '2.4 MB'
  chunk_count: number
  status: DocStatus
  uploaded_at: string
}

export const mockDocuments: KnowledgeDoc[] = [
  { id: 'd1', kb_id: '1', name: '产品白皮书.pdf', type: 'pdf', size: '2.4 MB', chunk_count: 86, status: 'completed', uploaded_at: '2 天前' },
  { id: 'd2', kb_id: '1', name: '用户手册 v3.docx', type: 'docx', size: '1.1 MB', chunk_count: 54, status: 'completed', uploaded_at: '2 天前' },
  { id: 'd3', kb_id: '1', name: '常见问题 FAQ.md', type: 'md', size: '12 KB', chunk_count: 8, status: 'completed', uploaded_at: '3 天前' },
  { id: 'd4', kb_id: '1', name: 'API 接入指南.md', type: 'md', size: '34 KB', chunk_count: 22, status: 'processing', uploaded_at: '刚刚' },
  { id: 'd5', kb_id: '1', name: '历史合同模板.pdf', type: 'pdf', size: '—', chunk_count: 0, status: 'failed', uploaded_at: '昨天' },
  { id: 'd6', kb_id: '1', name: '更新日志.txt', type: 'txt', size: '8 KB', chunk_count: 5, status: 'completed', uploaded_at: '上周' },
]

// ============================================================================
// 状态徽标元数据
// ============================================================================

interface StatusMeta {
  label: string
  dot: string
  pulse?: boolean
}

/** 文档状态徽标（DocumentList 用） */
export const docStatusMeta: Record<DocStatus, StatusMeta> = {
  pending: { label: '待处理', dot: 'bg-muted-foreground' },
  processing: { label: '处理中', dot: 'bg-warning', pulse: true },
  completed: { label: '就绪', dot: 'bg-success' },
  failed: { label: '失败', dot: 'bg-destructive' },
}

/** 知识库状态徽标（KnowledgeCard / KnowledgeDetailPage header 用） */
export const kbStatusMeta: Record<KnowledgeBaseStatus, StatusMeta> = {
  ready: { label: '就绪', dot: 'bg-success' },
  reindexing: { label: '重建中', dot: 'bg-warning', pulse: true },
}

// ============================================================================
// 检索测试（mock，等后端片6 检索接口接入后切换）
// ============================================================================

export interface RetrievalChunk {
  id: string
  doc_id: string
  doc_name: string
  /** 片段文本（v1 父子块策略下命中后端返回整段，此处 mock 用一段假文本） */
  content: string
  /** 相似度分数 0-1，越大越相关 */
  score: number
}

/** 几段示例 chunk 文本，按 mock query 假装匹配 */
const sampleChunks: { doc_name: string; content: string }[] = [
  {
    doc_name: '产品白皮书.pdf',
    content:
      '本产品采用混合检索架构，结合向量召回（pgvector）与全文检索（PostgreSQL FTS），通过 RRF 算法融合排序，再经过重排序模型精调，最终返回 topK 段落。',
  },
  {
    doc_name: 'API 接入指南.md',
    content:
      '集成 API 的第一步是在控制台「设置 → API」申请 API Key；所有请求需在 Header 中携带 `Authorization: Bearer <key>`，并使用 HTTPS 通信，避免 Key 泄漏。',
  },
  {
    doc_name: '用户手册 v3.docx',
    content:
      '知识库支持 md / txt 两种格式上传；上传后系统会自动切块（默认 ~512 token + 50 overlap），并调用配置的 embedding 模型生成向量索引，状态变为「就绪」后即可用于检索。',
  },
  {
    doc_name: '常见问题 FAQ.md',
    content:
      'Q: 文档上传后多久能用？A: 取决于文档大小与 embedding 模型速度，一般几秒到几分钟；状态从「处理中」转为「就绪」即可。',
  },
  {
    doc_name: 'API 接入指南.md',
    content:
      '检索接口 `/api/v1/knowledge-bases/{kb_id}/retrieve` 接受 `query` 与 `top_k` 参数，返回带相似度分数的 chunk 列表，可直接用作 LLM 上下文。',
  },
  {
    doc_name: '更新日志.txt',
    content:
      'v0.4: 新增 BAAI/bge-m3 与 BAAI/bge-large-zh-v1.5 双模型支持；优化中文切块策略，命中率提升约 12%。',
  },
]

/**
 * Mock 检索：500ms 延迟，返回 topK 条假命中（递减相似度）。
 * 不真做语义匹配，等后端片6 接入后改成真接口调用。
 */
export function runMockRetrieval(
  _query: string,
  _kbId: string,
  topK: number,
): Promise<RetrievalChunk[]> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const take = Math.min(topK, sampleChunks.length)
      const chunks: RetrievalChunk[] = sampleChunks.slice(0, take).map((c, i) => ({
        id: crypto.randomUUID(),
        doc_id: `mock-doc-${i}`,
        doc_name: c.doc_name,
        content: c.content,
        // 递减分数：0.92 / 0.85 / 0.78 / ...，最低 0.3
        score: Math.max(0.3, 0.92 - i * 0.07),
      }))
      resolve(chunks)
    }, 500)
  })
}
