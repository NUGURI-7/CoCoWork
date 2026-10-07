import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ListTree } from 'lucide-react'

import { MarkdownRender } from '@/components/chat/MarkdownRender'
import { Button } from '@/components/ui/button'
import { injectFigures } from '@/lib/figures'
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
 * 但渲染出来很高，按 char_length 猜会漏判。图片是异步加载的、加载完才把内容撑高，
 * 故用 ResizeObserver 盯内容高度，变了就重判。
 */
export function ParagraphCard({ paragraph, expanded, onToggle }: ParagraphCardProps) {
  // 内容层不受折叠限高约束，量它的自然高度；外层容器负责裁切
  const contentRef = useRef<HTMLDivElement>(null)
  const [overflowing, setOverflowing] = useState(false)

  useLayoutEffect(() => {
    const el = contentRef.current
    if (!el) return
    const measure = () => setOverflowing(el.offsetHeight > COLLAPSED_MAX_HEIGHT)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const content = useMemo(
    () => injectFigures(paragraph.content, paragraph.figures),
    [paragraph.content, paragraph.figures],
  )

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
          className="overflow-hidden"
          style={expanded ? undefined : { maxHeight: COLLAPSED_MAX_HEIGHT }}
        >
          <div ref={contentRef}>
            <MarkdownRender content={content} />
          </div>
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
