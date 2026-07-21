import type { RetrievalMode } from '@/types'

/** 检索模式中文名（知识库设置页选择器 / 命中测试展示共用） */
export const RETRIEVAL_MODE_LABEL: Record<RetrievalMode, string> = {
  vector: '向量检索',
  keyword: '关键词检索',
  hybrid: '混合检索',
}
