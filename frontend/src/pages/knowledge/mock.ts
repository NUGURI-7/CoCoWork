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
