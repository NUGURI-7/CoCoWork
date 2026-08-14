/**
 * 产物的公共动作与展示helper —— 消息内卡片（ArtifactCard）与产出物面板共用。
 *
 * 抽出来的理由：两处都要「换一个新鲜 URL 再打开 / 下载」，而这段逻辑里有几个
 * 容易写歪的细节（attachment 要用临时 <a> 不能 window.open、新标签页要带
 * noopener、换链接期间要禁重复点击）。留两份必然漂移。
 */

import { useState } from 'react'
import { File, FileImage, FileSpreadsheet, FileText } from 'lucide-react'
import { toast } from 'sonner'

import { getArtifactDownloadUrl } from '@/api/artifact'
import type { ArtifactDisposition } from '@/api/artifact'

/**
 * 站内预览的类型判定。
 *
 * **扩展名优先于 MIME**：产物的 content_type 是后端 `mimetypes.guess_type` 按
 * 文件名猜的，遇上冷门后缀会退成 `application/octet-stream`；而交付区是开放式
 * 回收（放进去什么收什么），这种情况迟早会撞上。扩展名是用户和 agent 都看得见
 * 的那个约定，拿它当第一依据更稳。
 */
export type PreviewKind =
  | 'pdf'
  | 'image'
  | 'svg'
  | 'markdown'
  | 'html'
  | 'csv'
  | 'json'
  | 'text'

/** 扩展名 → 预览方式。列在这儿的才有站内预览，其余一律新标签页打开。 */
const _PREVIEW_BY_EXT: Record<string, PreviewKind> = {
  pdf: 'pdf',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  gif: 'image',
  webp: 'image',
  bmp: 'image',
  ico: 'image',
  avif: 'image',
  svg: 'svg',
  md: 'markdown',
  markdown: 'markdown',
  html: 'html',
  htm: 'html',
  csv: 'csv',
  tsv: 'csv',
  json: 'json',
  txt: 'text',
  log: 'text',
  py: 'text',
  js: 'text',
  ts: 'text',
  tsx: 'text',
  jsx: 'text',
  sh: 'text',
  yaml: 'text',
  yml: 'text',
  toml: 'text',
  ini: 'text',
  sql: 'text',
  xml: 'text',
  css: 'text',
}

/** 拿扩展名不到时的兜底：认 MIME 的大类。 */
function _previewByMime(contentType: string): PreviewKind | null {
  if (contentType === 'application/pdf') return 'pdf'
  if (contentType === 'image/svg+xml') return 'svg'
  if (contentType.startsWith('image/')) return 'image'
  if (contentType === 'text/html') return 'html'
  if (contentType === 'text/markdown') return 'markdown'
  if (contentType === 'text/csv') return 'csv'
  if (contentType === 'application/json') return 'json'
  if (contentType.startsWith('text/')) return 'text'
  return null
}

/** 文本类预览要把整份内容读进内存再渲染，超过这个尺寸不划算，直接劝下载。 */
export const PREVIEW_TEXT_MAX_SIZE = 2 * 1024 * 1024

/** 这个产物能不能站内预览？能则返回预览方式，不能返回 null。 */
export function previewKindOf(
  filename: string,
  contentType: string,
): PreviewKind | null {
  const ext = filename.includes('.')
    ? filename.split('.').pop()!.toLowerCase()
    : ''
  return _PREVIEW_BY_EXT[ext] ?? _previewByMime(contentType)
}

/** 预览方式是不是「要先把文本读下来」那一类（相对于直接把 URL 交给浏览器）。 */
export function isTextKind(kind: PreviewKind): boolean {
  return kind !== 'pdf' && kind !== 'image'
}

/** MIME → 图标。前缀匹配优先，兜底通用文件图标。 */
export function iconFor(contentType: string) {
  if (contentType.startsWith('image/')) return FileImage
  if (contentType === 'text/csv' || contentType.includes('spreadsheet')) {
    return FileSpreadsheet
  }
  if (contentType.startsWith('text/')) return FileText
  return File
}

/** 字节数 → 人话。产物普遍是几十 KB，一位小数够用。 */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * 文件名 → 类型标签（`worker_week.svg` → `SVG`）。
 *
 * 优先用扩展名而不是 MIME：用户认得 `SVG`，不认得 `image/svg+xml`。
 * 没有扩展名时退回 MIME 的子类型，再没有就给个「文件」。
 */
export function formatKind(filename: string, contentType: string): string {
  const ext = filename.includes('.') ? filename.split('.').pop() : ''
  if (ext) return ext.toUpperCase()

  const subtype = contentType.split('/')[1]
  return subtype ? subtype.toUpperCase() : '文件'
}

/**
 * ISO 时间 → 列表里那一小行。今天只给时分，其余给月日 —— 面板窄，省字。
 */
export function formatArtifactTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()

  const pad = (n: number) => String(n).padStart(2, '0')
  return sameDay
    ? `${pad(d.getHours())}:${pad(d.getMinutes())}`
    : `${d.getMonth() + 1}月${d.getDate()}日`
}

/**
 * 打开 / 下载一个产物。
 *
 * **URL 不预先持有**，点了才向后端换一个短期预签名 —— 于是每次点击都过一遍
 * 归属校验，链接也不会长期有效，消息放三天再点照样能开。
 */
export function useArtifactActions(artifactId: string) {
  const [busy, setBusy] = useState(false)

  // 回调参数不叫 `use`：eslint 的 react-hooks 插件把 `use(...)` 一律当成 React
  // 的 use Hook，在普通函数里调就报 rules-of-hooks
  async function withUrl(
    disposition: ArtifactDisposition,
    consume: (url: string) => void,
  ) {
    if (busy) return
    setBusy(true)
    try {
      consume(await getArtifactDownloadUrl(artifactId, disposition))
    } catch (err) {
      toast.error('打开产物失败', {
        description: err instanceof Error ? err.message : String(err),
      })
    } finally {
      setBusy(false)
    }
  }

  /** 新标签页打开看。noopener,noreferrer：新页面拿不到 window.opener，碰不了本页。 */
  const open = () =>
    void withUrl('inline', (url) =>
      window.open(url, '_blank', 'noopener,noreferrer'),
    )

  /** 存到本地。用临时 <a> 而不是 window.open —— attachment 响应不会导航，
   *  window.open 会闪出一个空白标签页。 */
  const download = (e?: React.MouseEvent) => {
    e?.stopPropagation() // 别顺带触发外层的「打开」
    void withUrl('attachment', (url) => {
      const a = document.createElement('a')
      a.href = url
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
    })
  }

  return { busy, open, download }
}
