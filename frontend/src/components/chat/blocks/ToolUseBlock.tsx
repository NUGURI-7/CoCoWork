import { memo, useMemo } from 'react'
import { Wrench, XCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ToolUseBlock as ToolUseBlockType } from '@/types'

import { TOOL_LABELS, primaryArgSummary } from './tool-format'

interface ToolUseBlockProps {
  block: ToolUseBlockType
}

/**
 * Tool 调用块 —— 一行状态：图标 + 工具名 + 主参数摘要。
 * 参数与结果的原始内容不展示给使用者。
 */
export const ToolUseBlock = memo(function ToolUseBlock({
  block,
}: ToolUseBlockProps) {
  /** 一行摘要：主参数缩短 + 限长。流式中途 JSON 还不完整时留空。 */
  const summary = useMemo(
    () => primaryArgSummary(block.name, block.partialInputJson),
    [block.name, block.partialInputJson],
  )

  // 状态色：success 品牌绿、error 红、running 走 muted（同色一行，扳手 + 工具名整体）
  const statusColor =
    block.status === 'success'
      ? 'text-brand'
      : block.status === 'error'
        ? 'text-destructive'
        : 'text-muted-foreground'

  return (
    <div
      className={cn(
        '-mx-1 inline-flex max-w-full items-center gap-2 self-start rounded px-1 py-1 text-sm',
        statusColor,
      )}
    >
      <span className="flex shrink-0 items-center">
        {block.status === 'error' ? <XCircle size={14} /> : <Wrench size={14} />}
      </span>
      <span className="shrink-0 font-medium">
        {block.displayName ?? TOOL_LABELS[block.name] ?? block.name}
      </span>
      {summary && (
        <span className="text-muted-foreground/70 min-w-0 truncate font-mono text-xs">
          {summary}
        </span>
      )}
    </div>
  )
})
