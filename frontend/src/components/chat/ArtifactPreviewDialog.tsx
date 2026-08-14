import { useEffect, useMemo, useRef, useState } from 'react'
import DOMPurify from 'dompurify'
import { ring } from 'ldrs'
import { Code2, Download, Eye, ExternalLink } from 'lucide-react'

import {
  PREVIEW_TEXT_MAX_SIZE,
  formatSize,
  isTextKind,
  previewKindOf,
  useArtifactActions,
  type PreviewKind,
} from '@/components/chat/artifact-actions'
import { CodeBlock } from '@/components/chat/CodeBlock'
import { MarkdownRender } from '@/components/chat/MarkdownRender'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { getArtifactDownloadUrl } from '@/api/artifact'
import { cn } from '@/lib/utils'
import type { Artifact } from '@/types'

ring.register()

interface ArtifactPreviewDialogProps {
  /** null = 关着。传进来即打开，换一个即换预览对象 */
  artifact: Artifact | null
  onClose: () => void
}

/** 源码视图的语法高亮语言 —— CodeBlock 认的是 highlight.js 的语言名。 */
const _SOURCE_LANG: Record<PreviewKind, string> = {
  pdf: '',
  image: '',
  svg: 'xml',
  markdown: 'markdown',
  html: 'xml',
  csv: 'plaintext',
  json: 'json',
  text: 'plaintext',
}

/**
 * 极简 CSV 解析 —— 认 RFC 4180 的引号规则（`""` 是转义后的一个引号，引号内的
 * 逗号和换行都不算分隔符）。
 *
 * 不引第三方库：这里只要把表格画出来给人看一眼，不做类型推断、不做流式解析，
 * 而 papaparse 那一档是给「把 CSV 当数据用」准备的，为一个预览面板拖进来不值。
 */
function parseCsv(text: string, delimiter: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let inQuotes = false

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]

    if (inQuotes) {
      if (ch === '"') {
        // 连着两个引号 = 字段里真的有一个引号；单个引号 = 引号区间到此结束
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        field += ch
      }
      continue
    }

    if (ch === '"') {
      inQuotes = true
    } else if (ch === delimiter) {
      row.push(field)
      field = ''
    } else if (ch === '\n' || ch === '\r') {
      // \r\n 只当一个换行
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else {
      field += ch
    }
  }

  // 收尾：最后一行通常没有换行符结束
  if (field !== '' || row.length > 0) {
    row.push(field)
    rows.push(row)
  }
  return rows
}

/** 表格最多画这么多行 —— 再多 DOM 就该虚拟滚动了，而那是另一个量级的活。 */
const _CSV_MAX_ROWS = 500

function CsvTable({ text, delimiter }: { text: string; delimiter: string }) {
  const rows = useMemo(() => parseCsv(text, delimiter), [text, delimiter])
  if (rows.length === 0) return null

  const [header, ...body] = rows
  const shown = body.slice(0, _CSV_MAX_ROWS)

  return (
    <div className="p-4">
      <div className="border-border overflow-x-auto rounded-lg border">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-muted/60">
            <tr>
              {header.map((cell, i) => (
                <th
                  key={i}
                  className="border-border text-foreground border-b px-3 py-2 text-left font-medium whitespace-nowrap"
                >
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, ri) => (
              <tr key={ri} className="hover:bg-muted/30">
                {header.map((_, ci) => (
                  <td
                    key={ci}
                    className="border-border/60 text-muted-foreground border-b px-3 py-1.5 whitespace-nowrap"
                  >
                    {r[ci] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {body.length > shown.length && (
        <p className="text-muted-foreground/70 pt-2 text-xs">
          仅显示前 {_CSV_MAX_ROWS} 行，共 {body.length} 行 —— 完整内容请下载
        </p>
      )}
    </div>
  )
}

/**
 * SVG 预览 —— sanitize 之后内联进 DOM。
 *
 * **为什么不用 `<img src>`**：那样图里的文字选不中、也跟不了深色主题。内联能拿到
 * 完整的 DOM 能力，代价是 SVG 里可以藏 `<script>` / `onload=`，直接 innerHTML
 * 等于在自己的域上执行它。DOMPurify 把这些剥掉，只留下画图用的标签与属性。
 */
function SvgView({ text }: { text: string }) {
  const html = useMemo(
    () =>
      DOMPurify.sanitize(text, {
        USE_PROFILES: { svg: true, svgFilters: true },
      }),
    [text],
  )

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div
        // sanitize 过的内容，危险标签与事件属性已被剥离
        dangerouslySetInnerHTML={{ __html: html }}
        className="[&>svg]:h-auto [&>svg]:max-h-full [&>svg]:max-w-full"
      />
    </div>
  )
}

/**
 * HTML 预览 —— 关进一个匿名沙箱 iframe。
 *
 * `sandbox="allow-scripts"` 而**不给** `allow-same-origin`：iframe 落在 opaque
 * origin 上，脚本能跑（AI 产的报告常靠内联 JS 画图，全禁会渲染成白板），但它
 * 既读不到 cookie / localStorage，也访问不了父页面。其余能力（弹窗、表单、
 * 顶层跳转）一概不放开。
 *
 * 用 `srcDoc` 而不是 `src={url}`：URL 那条路会让这份 HTML 落在对象存储的域上，
 * 拿不到我们对 sandbox 的控制。
 */
function HtmlView({ text }: { text: string }) {
  return (
    <iframe
      title="HTML 预览"
      srcDoc={text}
      sandbox="allow-scripts"
      className="h-full w-full border-0 bg-white"
    />
  )
}

/**
 * 产物预览浮层。
 *
 * 两条取数路径，按类型分：
 * - PDF / 图片 → 只换一个短期 URL，交给浏览器自己渲染，不经过 JS
 * - 其余 → 换 URL 之后再 `fetch` 一次拿文本，喂给对应的渲染器
 *
 * 「预览 / 源码」切换只对文本类出现 —— PDF 和图片没有源码可看。
 */
export function ArtifactPreviewDialog({
  artifact,
  onClose,
}: ArtifactPreviewDialogProps) {
  const [url, setUrl] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showSource, setShowSource] = useState(false)

  const { busy, open: openInNewTab, download } = useArtifactActions(
    artifact?.id ?? '',
  )

  const kind = artifact
    ? previewKindOf(artifact.filename, artifact.content_type)
    : null
  const oversize = !!artifact && artifact.size > PREVIEW_TEXT_MAX_SIZE

  // 换产物就把视图切回预览态，否则会带着上一个文件的「源码」状态进来
  const artifactId = artifact?.id ?? null
  const lastIdRef = useRef<string | null>(null)
  if (lastIdRef.current !== artifactId) {
    lastIdRef.current = artifactId
    if (showSource) setShowSource(false)
  }

  useEffect(() => {
    if (!artifact || !kind) return

    let cancelled = false
    setLoading(true)
    setError(null)
    setUrl(null)
    setText(null)

    void (async () => {
      try {
        const fresh = await getArtifactDownloadUrl(artifact.id, 'inline')
        if (cancelled) return
        setUrl(fresh)

        // 文本类还要再拉一次内容；超限的不拉，界面上直接劝下载
        if (isTextKind(kind) && artifact.size <= PREVIEW_TEXT_MAX_SIZE) {
          const res = await fetch(fresh)
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          const body = await res.text()
          if (cancelled) return
          setText(body)
        }
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [artifact, kind])

  if (!artifact || !kind) return null

  const canToggleSource = isTextKind(kind) && text !== null

  function renderBody() {
    if (loading) {
      return (
        <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-3">
          <l-ring size="28" stroke="3" speed="2" color="currentColor" />
          <p className="text-xs">加载中…</p>
        </div>
      )
    }

    if (error) {
      return (
        <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
          <p className="text-sm">预览失败</p>
          <p className="text-xs opacity-70">{error}</p>
        </div>
      )
    }

    if (oversize && isTextKind(kind!)) {
      return (
        <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-sm">
            文件较大（{formatSize(artifact!.size)}），站内预览已跳过
          </p>
          <Button variant="outline" size="sm" onClick={download}>
            <Download size={14} />
            下载查看
          </Button>
        </div>
      )
    }

    if (showSource && text !== null) {
      return (
        <div className="p-4">
          <CodeBlock lang={_SOURCE_LANG[kind!]} source={text} />
        </div>
      )
    }

    switch (kind) {
      case 'pdf':
        return url ? (
          <iframe
            title={artifact!.filename}
            src={url}
            className="h-full w-full border-0"
          />
        ) : null

      case 'image':
        return url ? (
          <div className="flex h-full items-center justify-center p-6">
            <img
              src={url}
              alt={artifact!.filename}
              className="max-h-full max-w-full object-contain"
            />
          </div>
        ) : null

      case 'svg':
        return text !== null ? <SvgView text={text} /> : null

      case 'html':
        return text !== null ? <HtmlView text={text} /> : null

      case 'markdown':
        return text !== null ? (
          <div className="p-6">
            <MarkdownRender content={text} />
          </div>
        ) : null

      case 'csv':
        return text !== null ? (
          <CsvTable
            text={text}
            delimiter={artifact!.filename.toLowerCase().endsWith('.tsv') ? '\t' : ','}
          />
        ) : null

      case 'json':
      case 'text':
        return text !== null ? (
          <div className="p-4">
            <CodeBlock lang={_SOURCE_LANG[kind]} source={text} />
          </div>
        ) : null
    }
  }

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        showCloseButton={false}
        // 上限定死而不是一味吃满屏：产物要摊得开（图表 / 报告 / 网页），但大显示器上
        // 铺满 90vw 会让一份 Markdown 报告的行长到没法读。小屏才退回按视口比例算。
        className="flex h-[82vh] max-h-[820px] w-[88vw] max-w-[1080px] flex-col gap-0 overflow-hidden p-0 sm:max-w-[1080px]"
      >
        {/* 顶栏 */}
        <div className="border-border flex shrink-0 items-center gap-3 border-b px-4 py-2.5">
          <div className="flex min-w-0 flex-1 flex-col">
            <DialogTitle className="truncate text-sm font-medium">
              {artifact.filename}
            </DialogTitle>
            <DialogDescription className="text-[11px]">
              {formatSize(artifact.size)}
            </DialogDescription>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            {canToggleSource && (
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground h-7 gap-1.5 px-2 text-xs"
                onClick={() => setShowSource((v) => !v)}
              >
                {showSource ? <Eye size={14} /> : <Code2 size={14} />}
                {showSource ? '预览' : '源码'}
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              aria-label="在新标签页打开"
              disabled={busy}
              className="text-muted-foreground hover:text-foreground size-7"
              onClick={openInNewTab}
            >
              <ExternalLink size={14} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="下载"
              disabled={busy}
              className="text-muted-foreground hover:text-foreground size-7"
              onClick={download}
            >
              <Download size={14} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="关闭"
              className="text-muted-foreground hover:text-foreground size-7"
              onClick={onClose}
            >
              <span className="text-base leading-none">×</span>
            </Button>
          </div>
        </div>

        {/* 内容区。棋盘底给透明图片当背景，不然透明 PNG 在白底上看不出边界 */}
        <div className={cn('min-h-0 flex-1 overflow-auto', kind === 'image' && 'bg-muted/30')}>
          {renderBody()}
        </div>
      </DialogContent>
    </Dialog>
  )
}
