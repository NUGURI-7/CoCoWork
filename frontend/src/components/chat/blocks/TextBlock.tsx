import { memo, useMemo } from 'react'

import { injectCitations } from '@/lib/citations'
import { injectAnswerFigures } from '@/lib/figures'
import type { TextBlock as TextBlockType } from '@/types'

import { useChat } from '../ChatProvider'
import { CitationContext } from '../citation-context'
import { MarkdownRender } from '../MarkdownRender'

interface TextBlockProps {
  block: TextBlockType
  /** 这条回答的引用编号表（ref → 编号），由消息级算好传下来，编号跨文字块连续 */
  citeNumbers: Record<string, number>
}

/**
 * 文本块 —— assistant text 内容渲染。
 *
 * 极简：包一层 MarkdownRender，把 active 状态透传成 isStreaming
 * （触发末尾光标）。
 *
 * memo：流式那条消息每 token 重渲染，但已完成的块 block 引用不变（immer），
 * 靠 memo 跳过 —— 只有正在长的那个块重解析 markdown，其余块不动。
 *
 * 渲染前把知识库插图记号换成图片（见 injectAnswerFigures），引用记号换成
 * 角标（见 injectCitations）。
 */
export const TextBlock = memo(function TextBlock({ block, citeNumbers }: TextBlockProps) {
  const figureUrls = useChat((s) => s.figureUrls)
  const signing = useChat((s) => s.figureSigning > 0)
  const citationHits = useChat((s) => s.citationHits)
  const isStreaming = block.status === 'active'
  const content = useMemo(
    () =>
      injectCitations(
        injectAnswerFigures(block.content, figureUrls, signing, isStreaming),
        citeNumbers,
        isStreaming,
      ),
    [block.content, figureUrls, signing, isStreaming, citeNumbers],
  )

  return (
    <CitationContext.Provider value={citationHits}>
      <MarkdownRender content={content} isStreaming={isStreaming} />
    </CitationContext.Provider>
  )
})
