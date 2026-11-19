import { createContext, useContext, useMemo } from 'react'

import { numberCitations } from '@/lib/citations'
import type { KnowledgeHit, RenderBlock } from '@/types'

import { useChat } from './ChatProvider'

/**
 * 角标查出处用的表。由 TextBlock 提供，MarkdownRender 里的角标读它。
 *
 * 走 context 而不是让角标直接读 store：MarkdownRender 是通用组件，聊天之外
 * （知识库段落预览等）也在用；不在聊天里时读不到 context，角标退化成纯数字。
 */
export const CitationContext = createContext<Record<string, KnowledgeHit> | null>(null)

export function useCitationHit(ref: string): KnowledgeHit | undefined {
  return useContext(CitationContext)?.[ref]
}

/**
 * 一组块里引用的编号表（一条回答，或一张派活卡片里成员的汇报）。
 *
 * 流式时每个 token 都会重算，但只有出现新的引用时结果才变；按内容做稳定化，
 * 编号没变就返回同一个对象，已写完的文字块靠 memo 跳过重渲染。
 */
export function useCiteNumbers(blocks: RenderBlock[]): Record<string, number> {
  const hits = useChat((s) => s.citationHits)
  const texts = blocks.flatMap((b) => (b.type === 'text' ? [b.content] : []))
  const key = JSON.stringify(numberCitations(texts, hits))
  return useMemo(() => JSON.parse(key) as Record<string, number>, [key])
}
