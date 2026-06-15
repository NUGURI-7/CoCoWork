import { memo } from 'react'

import type { TextBlock as TextBlockType } from '@/types'

import { MarkdownRender } from '../MarkdownRender'

interface TextBlockProps {
  block: TextBlockType
}

/**
 * 文本块 —— assistant text 内容渲染。
 *
 * 极简：包一层 MarkdownRender，把 active 状态透传成 isStreaming
 * （触发末尾光标）。
 *
 * memo：流式那条消息每 token 重渲染，但已完成的块 block 引用不变（immer），
 * 靠 memo 跳过 —— 只有正在长的那个块重解析 markdown，其余块不动。
 */
export const TextBlock = memo(function TextBlock({ block }: TextBlockProps) {
  return (
    <MarkdownRender
      content={block.content}
      isStreaming={block.status === 'active'}
    />
  )
})
