import { memo, useState } from 'react'
import { ChevronDown, ListChecks, LoaderCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ThinkingBlock as ThinkingBlockType, ToolUseBlock as ToolUseBlockType } from '@/types'

import { ThinkingBlock } from './ThinkingBlock'
import { ToolUseBlock } from './ToolUseBlock'
import { TOOL_LABELS } from './tool-format'

export type ProcessBlock = ThinkingBlockType | ToolUseBlockType

/** 一串过程块 → 「思考 3 次 · 知识库《商品资料》×4 · 查询有效活动」 */
function summarize(blocks: ProcessBlock[]): string {
  let thinking = 0
  const tools = new Map<string, number>()
  for (const b of blocks) {
    if (b.type === 'thinking') {
      thinking += 1
      continue
    }
    const label = b.displayName ?? TOOL_LABELS[b.name] ?? b.name
    tools.set(label, (tools.get(label) ?? 0) + 1)
  }
  const parts = thinking ? [`思考 ${thinking} 次`] : []
  for (const [label, count] of tools) parts.push(count > 1 ? `${label} ×${count}` : label)
  return parts.join(' · ')
}

function isRunning(b: ProcessBlock): boolean {
  return b.type === 'thinking' ? b.status === 'active' : b.status === 'building' || b.status === 'calling'
}

/**
 * 两段正文之间连续的思考与工具调用，收成一行摘要，点开看明细。
 * 进行中时摘要随之更新，行首转圈；默认收起。
 */
export const ProcessGroup = memo(function ProcessGroup({ blocks }: { blocks: ProcessBlock[] }) {
  const [open, setOpen] = useState(false)
  const running = blocks.some(isRunning)

  return (
    <div className="max-w-full self-start">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-muted-foreground hover:text-foreground -mx-1 inline-flex max-w-full cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm transition-colors"
      >
        {running ? (
          <LoaderCircle size={14} className="shrink-0 animate-spin" />
        ) : (
          <ListChecks size={14} className="shrink-0" />
        )}
        <span className="text-foreground/80 truncate font-medium">{summarize(blocks)}</span>
        <ChevronDown
          size={12}
          className={cn('shrink-0 opacity-60 transition-transform duration-200', !open && '-rotate-90')}
        />
      </button>

      {open && (
        <div className="border-border mt-1 ml-1.5 flex flex-col gap-1 border-l pl-3">
          {blocks.map((b) =>
            b.type === 'thinking' ? (
              <ThinkingBlock key={b.index} block={b} />
            ) : (
              <ToolUseBlock key={b.index} block={b} />
            ),
          )}
        </div>
      )}
    </div>
  )
})
