import { useEffect, useState } from 'react'
import { ring } from 'ldrs'

import { getDocumentDownloadUrl } from '@/api/knowledge'
import { MarkdownRender } from '@/components/chat/MarkdownRender'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import type { Document } from '@/types'

ring.register()

interface DocumentPreviewSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kbId: string
  doc: Document | null
}

/**
 * 文档预览抽屉 —— 右滑 Sheet 展示 .md / .txt 文档的渲染后内容。
 *
 * 流程：open 翻 true → fetch download-url → fetch URL 拿文本 →
 * MarkdownRender 渲染。loading / error / 空内容三态兜底；关闭时清状态防串台。
 *
 * 只读，编辑能力 v2 接 tiptap 时一起做。PDF / docx 等二进制格式不在这片范围，
 * 上层调用方按文件扩展名决定是否暴露「预览」入口。
 */
export function DocumentPreviewSheet({
  open,
  onOpenChange,
  kbId,
  doc,
}: DocumentPreviewSheetProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !doc) return

    let cancelled = false
    setLoading(true)
    setError(null)
    setContent(null)

    ;(async () => {
      try {
        const { url } = await getDocumentDownloadUrl(kbId, doc.id)
        const res = await fetch(url)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const text = await res.text()
        if (cancelled) return
        setContent(text)
      } catch (err) {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : String(err)
        setError(msg)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [open, kbId, doc])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 sm:max-w-2xl"
      >
        <SheetHeader>
          <SheetTitle className="truncate">{doc?.name ?? '预览'}</SheetTitle>
          <SheetDescription>只读预览 · 编辑能力待后续版本</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex min-h-[200px] items-center justify-center">
              <l-ring size="32" stroke="3" speed="2" color="#2f6b53" />
            </div>
          )}
          {error && !loading && (
            <div className="flex flex-col gap-1 rounded-lg border p-4 text-sm">
              <div className="text-destructive font-medium">加载失败</div>
              <div className="text-muted-foreground font-mono text-xs break-all">
                {error}
              </div>
            </div>
          )}
          {!loading && !error && content !== null && (
            <MarkdownRender content={content} />
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
