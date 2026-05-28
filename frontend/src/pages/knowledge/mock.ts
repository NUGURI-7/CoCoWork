/** 知识库前端 mock。
 *
 * 知识库 + 文档接口均已接入后端，仅保留状态徽标元数据 + 检索测试 mock。
 */

import type { Document, KnowledgeBaseStatus } from '@/types'

// ============================================================================
// 状态徽标元数据
// ============================================================================

interface StatusMeta {
  label: string
  dot: string
  pulse?: boolean
}

/** 文档显示状态：把后端 (status, stage) 二维组合映射成单一展示态。 */
export type DocDisplayStatus =
  | 'uploading' // pending + stage=''（占位已建、字节未传完）
  | 'uploaded' // pending + stage='uploaded'（已传完、等向量化）
  | 'processing' // 向量化管线进行中
  | 'completed' // 向量化完成、可用
  | 'failed' // 任一阶段失败

/** 后端 Document → 单一展示态 */
export function getDocDisplayStatus(doc: Document): DocDisplayStatus {
  if (doc.status === 'failed') return 'failed'
  if (doc.status === 'completed') return 'completed'
  if (doc.status === 'processing') return 'processing'
  // status === 'pending'
  return doc.stage === 'uploaded' ? 'uploaded' : 'uploading'
}

/** 文档状态徽标（DocumentList 用，按 DocDisplayStatus 索引） */
export const docStatusMeta: Record<DocDisplayStatus, StatusMeta> = {
  uploading: { label: '上传中', dot: 'bg-muted-foreground', pulse: true },
  uploaded: { label: '待向量化', dot: 'bg-muted-foreground' },
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
