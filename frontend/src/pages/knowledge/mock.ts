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
  /** Badge 颜色覆盖类（在 outline 变体之上叠加 bg/text/border） */
  badgeClass?: string
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
  uploading: {
    label: '上传中',
    dot: 'bg-muted-foreground',
    pulse: true,
    badgeClass: 'bg-muted text-muted-foreground border-border',
  },
  uploaded: {
    label: '未向量化',
    dot: 'bg-muted-foreground',
    badgeClass: 'bg-muted text-muted-foreground border-border',
  },
  processing: {
    label: '向量化中',
    dot: 'bg-warning',
    pulse: true,
    badgeClass: 'bg-warning/15 text-warning-foreground border-warning/40',
  },
  completed: {
    label: '已向量化',
    dot: 'bg-success',
    badgeClass: 'bg-success/15 text-success border-success/40',
  },
  failed: {
    label: '失败',
    dot: 'bg-destructive',
    badgeClass: 'bg-destructive/15 text-destructive border-destructive/40',
  },
}

/** 知识库状态徽标（KnowledgeCard / KnowledgeDetailPage header 用） */
export const kbStatusMeta: Record<KnowledgeBaseStatus, StatusMeta> = {
  ready: { label: '就绪', dot: 'bg-success' },
  reindexing: { label: '重建中', dot: 'bg-warning', pulse: true },
}
