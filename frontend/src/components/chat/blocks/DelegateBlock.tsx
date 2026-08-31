import { memo, useEffect, useState } from 'react'
import { ChevronDown, User } from 'lucide-react'

import { cn } from '@/lib/utils'
import { softPalette } from '@/lib/avatar-color'
import type { DelegateBlock as DelegateBlockType } from '@/types'
import { useSubagentInfo } from '../SubagentDirectory'
import { TextBlock } from './TextBlock'
import { ThinkingBlock } from './ThinkingBlock'
import { FileOpsBlock } from './FileOpsBlock'
import { ToolUseBlock } from './ToolUseBlock'

interface DelegateBlockProps {
  block: DelegateBlockType
}

/**
 * 派活块 —— 管家把活分给某成员（子 agent），折叠展示该成员的实时执行过程。
 *
 * 头部：成员 pill（头像 + 真名 + 按成员哈希的柔和底色）+ 状态 + 折叠箭头
 * 展开：派的活（task）+ 子 agent 实时干活的块（text / thinking / tool_use 递归渲染）
 *
 * 折叠：local state，running 默认展开（看实时干活）；done / error 后自动折叠
 * （管家会在主流接着总结结果，过程默认收起、可手动展开回看）。
 */

export const DelegateBlock = memo(function DelegateBlock({
  block,
}: DelegateBlockProps) {
  const info = useSubagentInfo(block.subagentName)
  const label = info?.name || block.subagentName || '成员'
  const palette = softPalette(block.subagentName || label)
  const running = block.status === 'running'

  const [collapsed, setCollapsed] = useState(false)
  useEffect(() => {
    if (block.status === 'done' || block.status === 'error') setCollapsed(true)
  }, [block.status])

  const statusText =
    block.status === 'error' ? '出错' : running ? '干活中…' : '已完成'

  return (
    <div className="max-w-full self-start">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="-mx-1 inline-flex max-w-full cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm"
      >
        <span
          className={cn(
            'inline-flex shrink-0 items-center gap-1.5 rounded-full py-0.5 pr-2.5 pl-1 font-medium',
            palette,
          )}
        >
          <span className="flex h-5 w-5 items-center justify-center overflow-hidden rounded-full">
            {info?.avatarUrl ? (
              <img
                src={info.avatarUrl}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              <User size={12} />
            )}
          </span>
          {label}
        </span>

        <span className="text-muted-foreground shrink-0 text-xs">
          {statusText}
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
        <div className="border-border mt-1.5 ml-3 space-y-2 border-l pl-3">
          {block.task && (
            <p className="text-muted-foreground text-xs italic">{block.task}</p>
          )}
          {block.blocks.map((b) => {
            if (b.type === 'text')
              return <TextBlock key={b.index} block={b} />
            if (b.type === 'thinking')
              return <ThinkingBlock key={b.index} block={b} />
            if (b.type === 'file_ops')
              return <FileOpsBlock key={b.index} block={b} />
            if (b.type === 'tool_use')
              return <ToolUseBlock key={b.index} block={b} />
            return null
          })}
        </div>
      )}
    </div>
  )
})
