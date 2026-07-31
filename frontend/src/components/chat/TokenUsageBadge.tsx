import { Coins } from 'lucide-react'

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card'
import type { RenderBlock, TokenUsage, TokenUsageRow } from '@/types'

import { useSubagentDirectory, type SubagentInfo } from './SubagentDirectory'

/** 千分位 —— 五位数的 token 不加分隔符没法一眼读出量级 */
function fmt(n: number): string {
  return n.toLocaleString('en-US')
}

/** 明细里的一行：谁、干了什么、烧了多少 */
interface UsageLine {
  key: string
  /** 烧钱的主体：supervisor 或成员展示名 */
  who: string
  /** 那次派活的任务描述；supervisor 那行没有 */
  what: string
  total: number
}

/**
 * 后端只给 delegate_id + 两个数，成员名和任务描述在这儿从消息块里补齐。
 *
 * 同一份数据不存两遍：`delegate_id` 就是那个 task 工具的 tool_call_id，
 * 派活卡片（DelegateBlock.callId）本来就带着它。
 * 只扫顶层 —— 派活卡片恒在主流，子 agent 不会再派活。
 */
function toLines(
  rows: TokenUsageRow[],
  blocks: RenderBlock[],
  directory: Record<string, SubagentInfo>,
): UsageLine[] {
  const delegates = new Map<string, { subagentName: string; task: string }>()
  for (const b of blocks) {
    if (b.type === 'delegate') {
      delegates.set(b.callId, { subagentName: b.subagentName, task: b.task })
    }
  }

  return rows.map((row, i) => {
    const total = row.prompt_tokens + row.completion_tokens
    if (row.delegate_id === null) {
      return { key: `supervisor-${i}`, who: 'Supervisor', what: '', total }
    }
    const d = delegates.get(row.delegate_id)
    return {
      key: row.delegate_id,
      // 名册没登记（Playground）→ 降级显示技术 id；卡片都没找到 → 兜底文案
      who: d ? (directory[d.subagentName]?.name ?? d.subagentName) : '成员',
      what: d?.task ?? '',
      total,
    }
  })
}

/**
 * 本轮 token 消耗 —— 操作行上的一个数字，鼠标悬停展开明细。
 *
 * 口径是「累加」：一轮里模型被调好几次，每次都要把历史重新读一遍，这个数是
 * 全部调用相加（业界同口径：dify / letta 都这么算）。所以它**不等于**
 * 「上下文有多长」—— 同一段历史被读几遍就算几遍。
 *
 * 分行按「一次派活」而非「一个成员」：同一个成员被并发派两次是两件事，
 * 合并了就看不出哪次贵。
 */
export function TokenUsageBadge({
  usage,
  blocks,
}: {
  usage: TokenUsage
  blocks: RenderBlock[]
}) {
  const directory = useSubagentDirectory()
  const total = usage.prompt_tokens + usage.completion_tokens
  // provider 不回报用量（未开 stream_usage 的兼容端点）→ 整块不出现，不摆个 0 占位
  if (total === 0) return null

  const lines = toLines(usage.token_usage, blocks, directory)

  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <span
          tabIndex={0}
          role="button"
          aria-label={`本轮消耗 ${total} tokens`}
          className="text-muted-foreground hover:text-foreground hover:bg-muted flex h-7 cursor-default items-center gap-1 rounded-md px-1.5 text-xs tabular-nums transition-colors"
        >
          <Coins size={12} />
          {fmt(total)}
        </span>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="w-80 p-0 text-xs">
        <div className="flex items-baseline justify-between border-b px-3 py-2">
          <span className="text-muted-foreground">本轮消耗</span>
          <span className="font-medium tabular-nums">{fmt(total)}</span>
        </div>
        <ul className="max-h-64 overflow-y-auto py-1">
          {lines.map((line) => (
            <li key={line.key} className="flex items-baseline gap-2 px-3 py-1">
              <span className="shrink-0 font-medium">{line.who}</span>
              <span className="text-muted-foreground min-w-0 flex-1 truncate">
                {line.what}
              </span>
              <span className="shrink-0 tabular-nums">{fmt(line.total)}</span>
            </li>
          ))}
        </ul>
        <div className="text-muted-foreground border-t px-3 py-2 tabular-nums">
          输入 {fmt(usage.prompt_tokens)} · 输出 {fmt(usage.completion_tokens)}
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}
