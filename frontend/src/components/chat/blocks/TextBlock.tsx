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
 */
export function TextBlock({ block }: TextBlockProps) {
  return (
    <MarkdownRender
      content={block.content}
      isStreaming={block.status === 'active'}
    />
  )
}
