import { useMemo, type ReactNode } from 'react'
import { FileText } from 'lucide-react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { injectAnswerFigures } from '@/lib/figures'

import { useChat } from './ChatProvider'
import { useCitationHit } from './citation-context'
import { MarkdownRender } from './MarkdownRender'

interface CitationBadgeProps {
  citeRef: string
  /** 角标上显示的编号 */
  children: ReactNode
}

/**
 * 回答里的引用角标。点开是贴在角标旁的 Popover：出处一行 + 段落原文。
 *
 * 不用 Dialog：看一段来源不该遮住整页、打断阅读；点别处即关。
 */
export function CitationBadge({ citeRef, children }: CitationBadgeProps) {
  const hit = useCitationHit(citeRef)
  if (!hit) return <sup className="text-muted-foreground">[{children}]</sup>

  const location = [hit.title, hit.page !== null ? `第 ${hit.page} 页` : '']
    .filter(Boolean)
    .join(' · ')

  // 论文 / 维基百科式上标 [1]：<sup> 是 HTML 标准的上标元素，语义上就是脚注标记；
  // 方括号让相邻的 [1][2] 不会读成 12
  return (
    <sup className="leading-none">
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={`来源 ${String(children)}：${hit.doc_name}`}
            className="text-brand hover:bg-brand-subtle data-[state=open]:bg-brand-subtle cursor-pointer rounded-sm px-px font-medium tabular-nums transition-colors"
          >
            [{children}]
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[26rem] max-w-[calc(100vw-2rem)] p-0">
          <div className="border-border flex items-start gap-2 border-b px-4 py-3">
            <FileText size={14} className="text-muted-foreground mt-0.5 shrink-0" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{hit.doc_name}</p>
              {location && <p className="text-muted-foreground truncate text-xs">{location}</p>}
            </div>
          </div>
          <CitationExcerpt content={hit.content} />
        </PopoverContent>
      </Popover>
    </sup>
  )
}

/** 段落原文。段内插图记号复用回答那套换图逻辑，签名表是同一张 */
function CitationExcerpt({ content }: { content: string }) {
  const figureUrls = useChat((s) => s.figureUrls)
  const signing = useChat((s) => s.figureSigning > 0)
  const text = useMemo(
    () => injectAnswerFigures(content, figureUrls, signing, false),
    [content, figureUrls, signing],
  )
  return (
    <div className="max-h-72 overflow-y-auto px-4 py-3">
      {/* 段落原文常以章节标题开头，小卡片里按正文字号加粗显示，不抢内容 */}
      <MarkdownRender
        content={text}
        className="prose-sm prose-headings:mt-0 prose-headings:mb-2 prose-headings:text-sm prose-headings:font-semibold"
      />
    </div>
  )
}
