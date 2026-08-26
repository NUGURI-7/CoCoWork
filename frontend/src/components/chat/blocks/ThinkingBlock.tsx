import { memo, useEffect, useState } from 'react'
import { Brain, ChevronDown } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ThinkingBlock as ThinkingBlockType } from '@/types'

import { MarkdownRender } from '../MarkdownRender'

interface ThinkingBlockProps {
  block: ThinkingBlockType
}

/**
 * 思考块 —— DeepSeek-R1 reasoning / Anthropic extended thinking 渲染。
 *
 * 头部：Brain 图标（active 期 animate-pulse）+ 状态文案 + ChevronDown
 * 内容：弱底色折叠卡 + MarkdownRender（active 期透传光标）
 *
 * 折叠状态走 local state，store 的 block.collapsed 当初始默认值。
 * useEffect 监听 status 变 'done' 时自动折叠（思考完成默认收起、节省视觉空间）。
 */
export const ThinkingBlock = memo(function ThinkingBlock({
  block,
}: ThinkingBlockProps) {
  const [collapsed, setCollapsed] = useState(block.collapsed)
  const isActive = block.status === 'active'

  useEffect(() => {
    if (block.status === 'done') setCollapsed(true)
  }, [block.status])

  return (
    <div className="max-w-full self-start">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="text-muted-foreground hover:text-foreground -mx-1 inline-flex max-w-full cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm transition-colors"
      >
        <Brain size={14} className={cn('shrink-0', isActive && 'animate-pulse')} />
        <span className="text-foreground/80 shrink-0 font-medium whitespace-nowrap">
          {isActive ? '思考中…' : '已思考'}
        </span>
        <ChevronDown
          size={12}
          className={cn(
            'shrink-0 opacity-60 transition-transform duration-200',
            collapsed && '-rotate-90',
          )}
        />
      </button>

      {!collapsed && (
        <div className="bg-muted/50 mt-1.5 ml-5 rounded-md p-3">
          <MarkdownRender
            content={block.content}
            isStreaming={isActive}
            className="text-muted-foreground"
          />
        </div>
      )}
    </div>
  )
})
