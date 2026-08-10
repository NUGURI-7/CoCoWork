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
 * 所以段与段之间的边界要看得见：一段一张卡、卡头带序号与字数，默认折叠正文，
 * 一屏能扫到多个切点。
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

  // 定位信息：标题链（md）与页码（PDF）是同一类东西，两者都没有时整行不渲染
  const locators = [paragraph.title, paragraph.page != null && `第 ${paragraph.page} 页`]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="bg-card space-y-2 rounded-lg border p-4 shadow-sm">
      {/* 卡头：序号 + 定位信息 | 字数 · 子块数 */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-muted-foreground shrink-0 font-mono text-xs">
            #{paragraph.position + 1}
          </span>
          {locators && (
            <>
              <ListTree className="text-muted-foreground size-3.5 shrink-0" />
              <span className="text-muted-foreground truncate text-xs" title={locators}>
                {locators}
              </span>
            </>
          )}
        </div>
        <span className="text-muted-foreground shrink-0 font-mono text-xs">
          {paragraph.char_length} 字 · {paragraph.chunk_count} 子块
        </span>
      </div>

      {/* 正文：折叠时限高 + 底部渐隐，暗示「下面还有」 */}
      <div className="relative">
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
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-foreground h-7 w-full"
          onClick={onToggle}
        >
          <ChevronDown className={cn('size-4 transition-transform', expanded && 'rotate-180')} />
          {expanded ? '收起' : '展开全文'}
        </Button>
      )}
    </div>
  )
}
