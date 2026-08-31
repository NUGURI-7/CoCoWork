import { memo, useMemo, useState } from 'react'
import { ChevronDown, Files, XCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { FileOp, FileOpsBlock as FileOpsBlockType } from '@/types'

import { TOOL_LABELS, primaryArgSummary } from './tool-format'

interface FileOpsBlockProps {
  block: FileOpsBlockType
}

/** 折叠行里跟在「文件操作」后面的那段路径 —— 比单块那份短，因为前面还顶着状态词。 */
const HEAD_SUMMARY_MAX = 40

function label(op: FileOp): string {
  return TOOL_LABELS[op.name] ?? op.name
}

function isDone(op: FileOp): boolean {
  return op.status === 'success' || op.status === 'error'
}

/**
 * 文件操作组 —— 一串连续的 ls / read_file / write_file / edit_file / glob / grep
 * 收成一条活动行。
 *
 * 存在的理由：skill 执行期间这类调用一次回复能刷十几条，单条不携带用户关心的
 * 信息，各占一张卡片会把真正的正文顶出屏幕。所以默认折叠成一行，要追细节再展开。
 *
 * 折叠行跟着最新那条走（「读取 SKILL.md」），全部结束后收成计数（「12 次」）——
 * 进行中报当前动作是给人看进度的，都结束了再报动作就没有意义了。
 *
 * **失败不藏**：有 error 的操作在折叠行上留标记并染红，否则这一组把失败一起
 * 折进去，用户只会看到后面莫名其妙的结果、找不到起因。
 */
export const FileOpsBlock = memo(function FileOpsBlock({
  block,
}: FileOpsBlockProps) {
  const [collapsed, setCollapsed] = useState(block.collapsed)

  const ops = block.ops
  const errorCount = useMemo(
    () => ops.filter((o) => o.status === 'error').length,
    [ops],
  )
  const running = useMemo(() => ops.some((o) => !isDone(o)), [ops])

  /** 进行中报最新那条在干什么，全结束后报总数。 */
  const summary = useMemo(() => {
    if (!running) return `${ops.length} 次`
    const current = ops[ops.length - 1]
    if (!current) return ''
    const arg = primaryArgSummary(
      current.name,
      current.partialInputJson,
      HEAD_SUMMARY_MAX,
    )
    return arg ? `${label(current)} ${arg}` : label(current)
  }, [ops, running])

  const statusColor = errorCount
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
          {errorCount ? <XCircle size={14} /> : <Files size={14} />}
        </span>

        <span className="shrink-0 font-medium">文件操作</span>

        {summary && (
          <span className="text-muted-foreground/70 min-w-0 truncate font-mono text-xs">
            {summary}
          </span>
        )}

        {errorCount > 0 && (
          <span className="text-destructive shrink-0 text-xs">
            {errorCount} 个失败
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
        <div className="bg-muted/50 mt-1.5 ml-5 space-y-1 rounded-md p-3 text-xs">
          {ops.map((op) => (
            <FileOpRow key={op.index} op={op} />
          ))}
        </div>
      )}
    </div>
  )
})

/**
 * 明细里的一条 —— 状态点 + 中文名 + 操作对象。
 *
 * 失败的那条额外把后端给的结果摘要跟在下面：展开就是为了查失败，这时候还要
 * 再点一层才看得到原因，等于没展开。成功的不显示结果 —— 读文件的内容动辄几百行，
 * 铺在对话流里是灾难，真要看内容那是产物卡片的事。
 */
const FileOpRow = memo(function FileOpRow({ op }: { op: FileOp }) {
  const arg = useMemo(
    () => primaryArgSummary(op.name, op.partialInputJson),
    [op.name, op.partialInputJson],
  )

  const dotColor =
    op.status === 'success'
      ? 'bg-brand'
      : op.status === 'error'
        ? 'bg-destructive'
        : 'bg-muted-foreground/40'

  return (
    <div>
      <div className="flex items-center gap-2">
        <span className={cn('size-1.5 shrink-0 rounded-full', dotColor)} />
        <span className="text-muted-foreground shrink-0">{label(op)}</span>
        {arg && (
          <span className="text-muted-foreground/70 min-w-0 truncate font-mono">
            {arg}
          </span>
        )}
      </div>
      {op.status === 'error' && op.resultSummary && (
        <p className="text-destructive mt-0.5 ml-3.5 break-words">
          {op.resultSummary}
        </p>
      )}
    </div>
  )
})
