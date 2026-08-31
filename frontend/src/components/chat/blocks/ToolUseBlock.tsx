import { memo, useEffect, useMemo, useState } from 'react'
import { ChevronDown, Wrench, XCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ToolUseBlock as ToolUseBlockType } from '@/types'

import { TOOL_LABELS, primaryArgSummary } from './tool-format'

interface ToolUseBlockProps {
  block: ToolUseBlockType
}

/**
 * Tool 调用块 —— assistant tool_use 状态机渲染（building → calling → success/error）。
 *
 * 头部：状态图标 + 工具名 + 折叠箭头
 * 展开：参数（partial_json 美化）+ 结果（resultData 美化、非空才显）
 *
 * 折叠：local state + initial = block.collapsed；status 从运行态变终态时
 * 自动折叠（执行完成默认收起、用户已经看到参数 / 结果浮现过）。
 */
export const ToolUseBlock = memo(function ToolUseBlock({
  block,
}: ToolUseBlockProps) {
  const [collapsed, setCollapsed] = useState(block.collapsed)

  useEffect(() => {
    if (block.status === 'success' || block.status === 'error') {
      setCollapsed(true)
    }
  }, [block.status])

  const inputJsonText = useMemo(() => {
    const raw = block.partialInputJson
    if (!raw) return '(无参数)'
    try {
      return JSON.stringify(JSON.parse(raw), null, 2)
    } catch {
      return raw
    }
  }, [block.partialInputJson])

  /** 折叠头部的一行摘要：主参数缩短 + 限长。流式中途 JSON 还不完整时留空。 */
  const summary = useMemo(
    () => primaryArgSummary(block.name, block.partialInputJson),
    [block.name, block.partialInputJson],
  )

  const resultText = useMemo(() => {
    const d = block.resultData
    if (d === null || d === undefined) return ''
    if (typeof d === 'string') return d
    try {
      return JSON.stringify(d, null, 2)
    } catch {
      return String(d)
    }
  }, [block.resultData])

  const hasResult = block.resultData !== null && block.resultData !== undefined

  // 状态色：success 品牌绿、error 红、running 走 muted（同色一行，扳手 + 工具名整体）
  const statusColor =
    block.status === 'success'
      ? 'text-brand'
      : block.status === 'error'
        ? 'text-destructive'
        : 'text-muted-foreground'

  return (
    <div className="max-w-full self-start">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className={cn(
          '-mx-1 inline-flex max-w-full cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm transition-colors',
          statusColor,
        )}
      >
        <span className="flex shrink-0 items-center">
          {block.status === 'error' ? (
            <XCircle size={14} />
          ) : (
            <Wrench size={14} />
          )}
        </span>

        <span className="shrink-0 font-medium">
          {block.displayName ?? TOOL_LABELS[block.name] ?? block.name}
        </span>

        {summary && (
          <span className="text-muted-foreground/70 min-w-0 truncate font-mono text-xs">
            {summary}
          </span>
        )}

        <ChevronDown
          size={12}
          className={cn(
            'shrink-0 opacity-60 transition-transform duration-200',
            collapsed && '-rotate-90',
          )}
        />
      </button>

      {!collapsed && (
        <div className="bg-muted/50 mt-1.5 ml-5 space-y-2 rounded-md p-3 text-xs">
          <div>
            <div className="text-muted-foreground mb-1">参数</div>
            <pre className="bg-background/60 overflow-x-auto rounded p-2 break-words whitespace-pre-wrap">
              {inputJsonText}
            </pre>
          </div>

          {hasResult && (
            <div>
              <div className="text-muted-foreground mb-1">结果</div>
              <pre className="bg-background/60 max-h-64 overflow-x-auto rounded p-2 break-words whitespace-pre-wrap">
                {resultText}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
})
