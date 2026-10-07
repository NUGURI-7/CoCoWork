import { useLayoutEffect, useRef, useState } from 'react'
import { ChevronDown, ListTree } from 'lucide-react'

import { MarkdownRender } from '@/components/chat/MarkdownRender'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Paragraph } from '@/types'

/** 折叠态的正文最大高度（px）。约 9 行正文，一屏能看到三四段的边界。 */
const COLLAPSED_MAX_HEIGHT = 220

interface ParagraphCardProps {
  paragraph: Paragraph
  /** 受控展开态：由页面级的「全部展开 / 全部收起」统一驱动 */
  expanded: boolean
  onToggle: () => void
}

/**
 * 单个段的展示卡片。
 *
 * 这个页面的用途是**检查切得对不对**，不是读文档（读原文有文档列表里的预览抽屉），
 * 所以段与段之间的边界要看得见：一段一张卡，卡头是带底色的标题栏（序号徽标 + 标题链 +
 * 页码 | 字数）。行宽由页面列宽控制，卡内不再限宽。展开态由页面统一控制，默认展开。
 *
 * 「要不要显示展开按钮」靠实测高度而非字数阈值 —— 一个 markdown 表格可能字数不多
 * 但渲染出来很高，按 char_length 猜会漏判。
 */
export function ParagraphCard({ paragraph, expanded, onToggle }: ParagraphCardProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const [overflowing, setOverflowing] = useState(false)

  // 渲染后量一次实际高度，超过折叠高度才给展开按钮。
  // 依赖 content：翻页复用同一个组件实例时要重新量。
  useLayoutEffect(() => {
    const el = bodyRef.current
    if (!el) return
    setOverflowing(el.scrollHeight > COLLAPSED_MAX_HEIGHT)
  }, [paragraph.content])

  return (
    <div className="bg-card overflow-hidden rounded-lg border shadow-sm">
      {/* 卡头标题栏：序号徽标 + 标题链 + 页码 | 字数 · 子块数 */}
      <div className="bg-muted/50 flex items-center justify-between gap-3 border-b px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="bg-brand-subtle text-brand shrink-0 rounded px-1.5 py-0.5 font-mono text-xs font-medium">
            #{paragraph.position + 1}
          </span>
          {paragraph.title && (
            <>
              <ListTree className="text-muted-foreground size-3.5 shrink-0" />
              <span
                className="text-foreground truncate text-sm font-medium"
                title={paragraph.title}
              >
                {paragraph.title}
              </span>
            </>
          )}
          {paragraph.page != null && (
            <span className="text-muted-foreground shrink-0 text-xs">
              第 {paragraph.page} 页
            </span>
          )}
        </div>
        <span className="text-muted-foreground shrink-0 font-mono text-xs">
          {paragraph.char_length} 字 · {paragraph.chunk_count} 子块
        </span>
      </div>

      {/* 正文：折叠时限高 + 底部渐隐，暗示「下面还有」 */}
      <div className="relative px-4 py-3">
        <div
          ref={bodyRef}
          className="overflow-hidden"
          style={expanded ? undefined : { maxHeight: COLLAPSED_MAX_HEIGHT }}
        >
          <MarkdownRender content={paragraph.content} />
        </div>
        {!expanded && overflowing && (
          <div className="from-card pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t to-transparent" />
        )}
      </div>

      {overflowing && (
        <div className="px-4 pb-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground h-7 w-full"
            onClick={onToggle}
          >
            <ChevronDown className={cn('size-4 transition-transform', expanded && 'rotate-180')} />
            {expanded ? '收起' : '展开全文'}
          </Button>
        </div>
      )}
    </div>
  )
}
