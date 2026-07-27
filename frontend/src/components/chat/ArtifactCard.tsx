import { useState } from 'react'
import {
  Download,
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
} from 'lucide-react'
import { toast } from 'sonner'

import { getArtifactDownloadUrl } from '@/api/artifact'
import type { ArtifactDisposition } from '@/api/artifact'
import { cn } from '@/lib/utils'
import type { Artifact } from '@/types'

/**
 * 沙箱产物卡片 —— agent 这一轮交付出来的一个文件。
 *
 * 两个动作，各换各的链接：
 * - 点卡片主体 → 新标签页打开看（inline，浏览器直接渲染 SVG / 图片 / 文本）
 * - 点下载图标 → 存到本地（attachment）
 *
 * **URL 不预先持有**，点了才向后端换一个短期预签名。所以消息放三天再点也能开，
 * 且每次点击都过一遍后端的归属校验。
 *
 * 站内预览（不跳出对话）挂账未做，见 issues/003 —— 那一刀只是把同一个 URL
 * 换个容器渲染，不影响这里的形态。
 */

/** MIME → 图标。前缀匹配优先，兜底通用文件图标。 */
function iconFor(contentType: string) {
  if (contentType.startsWith('image/')) return FileImage
  if (contentType === 'text/csv' || contentType.includes('spreadsheet')) {
    return FileSpreadsheet
  }
  if (contentType.startsWith('text/')) return FileText
  return File
}

/** 字节数 → 人话。产物普遍是几十 KB，一位小数够用。 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const [busy, setBusy] = useState(false)
  const Icon = iconFor(artifact.content_type)

  /** 换一个新鲜 URL 再交给 use 处理；换链接期间禁重复点击。 */
  async function withUrl(
    disposition: ArtifactDisposition,
    use: (url: string) => void,
  ) {
    if (busy) return
    setBusy(true)
    try {
      use(await getArtifactDownloadUrl(artifact.id, disposition))
    } catch (err) {
      toast.error('打开产物失败', {
        description: err instanceof Error ? err.message : String(err),
      })
    } finally {
      setBusy(false)
    }
  }

  const handleOpen = () =>
    // noopener,noreferrer：新页面拿不到 window.opener，碰不了本页
    withUrl('inline', (url) => window.open(url, '_blank', 'noopener,noreferrer'))

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation() // 别顺带触发卡片的「打开」
    void withUrl('attachment', (url) => {
      // 用临时 <a> 而不是 window.open：attachment 响应不会导航，
      // 浏览器直接下载，也不会闪出一个空白标签页
      const a = document.createElement('a')
      a.href = url
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
    })
  }

  return (
    <button
      type="button"
      onClick={handleOpen}
      disabled={busy}
      title={`${artifact.filename} —— 点击在新标签页打开`}
      className={cn(
        'group/artifact border-border bg-muted/40 flex w-full max-w-md items-center gap-3',
        'rounded-lg border px-3 py-2.5 text-left transition-colors',
        'hover:bg-muted disabled:opacity-60',
      )}
    >
      <span className="bg-background text-muted-foreground flex h-9 w-9 shrink-0 items-center justify-center rounded-md">
        <Icon size={18} />
      </span>

      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-foreground truncate text-sm font-medium">
          {artifact.filename}
        </span>
        <span className="text-muted-foreground text-xs">
          {formatSize(artifact.size)}
        </span>
      </span>

      <span
        role="button"
        tabIndex={0}
        aria-label="下载"
        onClick={handleDownload}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') handleDownload(e as never)
        }}
        className={cn(
          'text-muted-foreground hover:text-foreground hover:bg-background',
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors',
        )}
      >
        <Download size={16} />
      </span>
    </button>
  )
}
