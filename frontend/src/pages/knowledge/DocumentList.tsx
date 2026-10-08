import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import dayjs from 'dayjs'
import {
  Download,
  Eye,
  FileText,
  Inbox,
  LayoutList,
  MoreHorizontal,
  ScanText,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  batchDeleteDocuments,
  batchIndexDocuments,
  batchParseDocuments,
  deleteDocument,
  getDocumentDownloadUrl,
  triggerIndexDocument,
  triggerParseDocument,
} from '@/api/knowledge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { triggerDownload } from '@/lib/download'
import { cn } from '@/lib/utils'
import { PARSE_BACKEND_LABELS, type Document } from '@/types'
import { DocumentPreviewSheet } from './DocumentPreviewSheet'
import { docStatusMeta, getDocDisplayStatus, type DocDisplayStatus } from './mock'

interface DocumentListProps {
  kbId: string
  docs: Document[]
  /** 删除成功后回调，父组件用来 refetch 文档列表 */
  onDeleted?: () => void
  /** 触发解析 / 建索引成功后回调，父组件乐观更新 + 启动轮询 */
  onProcessed?: (docId: string) => void
}

/**
 * 要不要显示这份文档的解析方式。
 *
 * 只对已解析完的 PDF 显示：md / txt 两条路结果完全一致（云端对纯文本没有增量，
 * `get_parser` 直接落回本地），标出来是噪声；没跑过的文档字段还是默认值，不是事实。
 *
 * 刻意**不判断「是否降级」**——那要拿库设置去推，而库设置事后可改：
 * 建库时选 local 传的文档，改成 baidu 后会被冤枉成「降级」。只显示存下来的事实，
 * 该不该重跑由人对着库设置自己判断。
 */
function showsParseBackend(doc: Document): boolean {
  return doc.file_type === 'pdf' && (doc.status === 'parsed' || doc.status === 'completed')
}

/** 能点「解析」的展示态（与后端 `_PARSABLE` 一致）：已解析 / 已完成 = 重新解析，失败的任一步都能重新解析 */
const PARSABLE: ReadonlySet<DocDisplayStatus> = new Set([
  'uploaded', 'parsed', 'completed', 'parse_failed', 'index_failed',
])

/** 能点「建索引」的展示态（与后端 `_INDEXABLE` 一致）：解析那步失败须先重新解析 */
const INDEXABLE: ReadonlySet<DocDisplayStatus> = new Set(['parsed', 'completed', 'index_failed'])

const PARSE_LABEL: Partial<Record<DocDisplayStatus, string>> = {
  uploaded: '解析',
  parsed: '重新解析',
  completed: '重新解析',
  parse_failed: '重试解析',
  index_failed: '重新解析',
}

const INDEX_LABEL: Partial<Record<DocDisplayStatus, string>> = {
  parsed: '建索引',
  completed: '重建索引',
  index_failed: '重试建索引',
}

/** 重新解析已完成文档的后果说明（单个 / 批量确认框共用） */
const REPARSE_CONSEQUENCE =
  '解析完成后，需要再点「建索引」才能恢复检索。'

export function DocumentList({ kbId, docs, onDeleted, onProcessed }: DocumentListProps) {
  // 选中态：Set 存选中的 doc id，查/增/删都 O(1)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchConfirmOpen, setBatchConfirmOpen] = useState(false)
  const [batchTriggering, setBatchTriggering] = useState(false)
  const [batchParseConfirmOpen, setBatchParseConfirmOpen] = useState(false)
  const [batchDeleting, setBatchDeleting] = useState(false)
  // 预览态：单实例 Sheet 共享，按 doc 切换
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null)

  const allSelected = docs.length > 0 && selected.size === docs.length
  const someSelected = selected.size > 0 && !allSelected

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev) // 复制再改，不原地改 state（React 靠引用变化判断更新）
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected((prev) =>
      prev.size === docs.length ? new Set() : new Set(docs.map((d) => d.id)),
    )
  }

  function clearSelection() {
    setSelected(new Set())
  }

  // 选中的文档里已建好索引的个数：批量解析会清掉它们的索引，非零就先确认
  const selectedCompleted = docs.filter((d) => selected.has(d.id) && d.status === 'completed').length

  async function runBatch(action: 'parse' | 'index') {
    if (batchTriggering) return
    setBatchTriggering(true)
    try {
      const run = action === 'parse' ? batchParseDocuments : batchIndexDocuments
      const verb = action === 'parse' ? '解析' : '建索引'
      const { triggered, skipped } = await run(kbId, [...selected])
      // 每个被触发的 doc 复用单个版乐观更新（父级标 processing + 启动轮询）
      triggered.forEach((id) => onProcessed?.(id))
      if (triggered.length) toast.success(`已触发 ${triggered.length} 个文档${verb}`)
      if (skipped.length) toast.warning(`${skipped.length} 个文档当前状态不能${verb}，已跳过`)
      setBatchParseConfirmOpen(false)
      clearSelection()
    } catch {
      // silent，失败不清选中
    } finally {
      setBatchTriggering(false)
    }
  }

  function handleBatchParse() {
    if (selectedCompleted > 0) setBatchParseConfirmOpen(true)
    else runBatch('parse')
  }

  async function handleBatchDelete() {
    setBatchDeleting(true)
    try {
      const { deleted } = await batchDeleteDocuments(kbId, [...selected])
      toast.success(`已删除 ${deleted} 个文档`)
      setBatchConfirmOpen(false)
      clearSelection()
      onDeleted?.()
    } catch {
      // 拦截器已 toast
    } finally {
      setBatchDeleting(false)
    }
  }

  if (docs.length === 0) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-sm">
        <Inbox className="size-8 opacity-40" />
        <p>还没有文档</p>
        <p className="text-xs">点击右上角「上传文档」开始</p>
      </div>
    )
  }

  return (
    <TooltipProvider delayDuration={200}>
    <div className="space-y-2">
      {/* 批量操作栏：选中 ≥1 时浮出 */}
      {selected.size > 0 && (
        <div className="bg-brand-subtle flex items-center gap-2 rounded-lg border px-4 py-2">
          <span className="text-brand text-sm font-medium">已选 {selected.size} 个</span>
          <div className="flex-1" />
          <Button size="sm" variant="outline" disabled={batchTriggering} onClick={handleBatchParse}>
            <ScanText className="size-4" />
            批量解析
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={batchTriggering}
            onClick={() => runBatch('index')}
          >
            <Sparkles className="size-4" />
            批量建索引
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-destructive hover:text-destructive"
            onClick={() => setBatchConfirmOpen(true)}
          >
            <Trash2 className="size-4" />
            批量删除
          </Button>
          <Button size="icon" variant="ghost" className="size-7" onClick={clearSelection}>
            <X className="size-4" />
          </Button>
        </div>
      )}

      <div className="divide-y rounded-lg border">
        {/* 全选行 */}
        <div className="text-muted-foreground flex items-center gap-3 px-4 py-2 text-xs">
          <Checkbox
            checked={allSelected ? true : someSelected ? 'indeterminate' : false}
            onCheckedChange={toggleAll}
            aria-label="全选"
          />
          <span>全选（{docs.length}）</span>
        </div>

        {docs.map((d) => (
          <DocumentRow
            key={d.id}
            kbId={kbId}
            doc={d}
            showBackend={showsParseBackend(d)}
            selected={selected.has(d.id)}
            onToggle={() => toggleOne(d.id)}
            onDeleted={onDeleted}
            onProcessed={onProcessed}
            onPreview={() => setPreviewDoc(d)}
          />
        ))}
      </div>

      {/* 文档预览抽屉（单实例共享） */}
      <DocumentPreviewSheet
        open={previewDoc !== null}
        onOpenChange={(o) => {
          if (!o) setPreviewDoc(null)
        }}
        kbId={kbId}
        doc={previewDoc}
      />

      {/* 批量解析确认：选中里有已建好索引的才弹 */}
      <AlertDialog open={batchParseConfirmOpen} onOpenChange={setBatchParseConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>解析选中的 {selected.size} 个文档？</AlertDialogTitle>
            <AlertDialogDescription>
              所选文档中有 {selectedCompleted} 个已建好索引，重新解析将清除它们的段落和索引，
              知识库将检索不到它们的内容。{REPARSE_CONSEQUENCE}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchTriggering}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={batchTriggering}
              onClick={(e) => {
                e.preventDefault()
                runBatch('parse')
              }}
            >
              {batchTriggering ? '提交中…' : '重新解析'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 批量删除确认 */}
      <AlertDialog open={batchConfirmOpen} onOpenChange={setBatchConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除选中的 {selected.size} 个文档？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。这些文档及其段落与索引将一并清除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchDeleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={batchDeleting}
              onClick={(e) => {
                e.preventDefault()
                handleBatchDelete()
              }}
              variant="destructive"
            >
              {batchDeleting ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
    </TooltipProvider>
  )
}

function DocumentRow({
  kbId,
  doc,
  showBackend,
  selected,
  onToggle,
  onDeleted,
  onProcessed,
  onPreview,
}: {
  kbId: string
  doc: Document
  showBackend: boolean
  selected: boolean
  onToggle: () => void
  onDeleted?: () => void
  onProcessed?: (docId: string) => void
  onPreview: () => void
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [reparseConfirmOpen, setReparseConfirmOpen] = useState(false)

  const display = getDocDisplayStatus(doc)
  const s = docStatusMeta[display]
  const parseLabel = PARSABLE.has(display) ? PARSE_LABEL[display] : undefined
  const indexLabel = INDEXABLE.has(display) ? INDEX_LABEL[display] : undefined
  const canPreview = isPreviewable(doc.name)

  async function runTrigger(action: 'parse' | 'index') {
    if (triggering) return
    setTriggering(true)
    try {
      if (action === 'parse') await triggerParseDocument(kbId, doc.id)
      else await triggerIndexDocument(kbId, doc.id)
      toast.success(`已触发「${doc.name}」${action === 'parse' ? '解析' : '建索引'}`)
      setReparseConfirmOpen(false)
      onProcessed?.(doc.id)
    } catch {
      // 拦截器已 toast（状态不允许 / 队列不可用的原因由后端给出）
    } finally {
      setTriggering(false)
    }
  }

  function handleParse() {
    // 已建好索引的文档重新解析会清掉索引、暂时检索不到，先确认
    if (display === 'completed') setReparseConfirmOpen(true)
    else runTrigger('parse')
  }

  async function handleDownload() {
    if (downloading) return
    setDownloading(true)
    try {
      triggerDownload(await getDocumentDownloadUrl(kbId, doc.id), doc.name)
    } catch {
      // 拦截器已 toast
    } finally {
      setDownloading(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteDocument(kbId, doc.id)
      toast.success(`文档「${doc.name}」已删除`)
      setConfirmOpen(false)
      onDeleted?.()
    } catch {
      // 拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div
        className={cn(
          'group flex items-center gap-3 px-4 py-3 transition-colors',
          selected ? 'bg-brand-subtle' : 'hover:bg-muted/40',
        )}
      >
        <Checkbox checked={selected} onCheckedChange={onToggle} aria-label={`选择 ${doc.name}`} />
        <FileText className="text-muted-foreground size-4 shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{doc.name}</div>
          <div className="text-muted-foreground mt-0.5 truncate text-xs">
            {formatBytes(doc.size)}
            {doc.paragraph_count > 0 && ` · ${doc.paragraph_count} 段`}
            {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
          </div>
        </div>

        {/* 解析方式 Badge —— 配色比状态 Badge 淡一档：它是背景信息，不该跟状态抢注意力 */}
        {showBackend && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge
                variant="outline"
                className="text-muted-foreground border-border/60 hidden shrink-0 font-normal sm:inline-flex"
              >
                {PARSE_BACKEND_LABELS[doc.parse_backend]}
              </Badge>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              这份文档实际用的解析方式。与库设置不一致时，重新解析即可按新设置再解析一次。
            </TooltipContent>
          </Tooltip>
        )}

        {/* 状态 Badge —— processing/uploading 时附脉动 dot */}
        <Badge variant="outline" className={cn('shrink-0 gap-1.5', s.badgeClass)}>
          {s.pulse && (
            <span className={cn('size-1.5 rounded-full', s.dot, 'animate-pulse')} />
          )}
          {s.label}
        </Badge>

        <span className="text-muted-foreground hidden w-16 text-right text-xs md:block">
          {dayjs(doc.created_at).fromNow()}
        </span>

        {/* 快捷按钮组：hover/focus 时显示 */}
        <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          {/* 分段：解析过、有段落就能看（待建索引时正是用来审段落的） */}
          {doc.paragraph_count > 0 && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground size-7"
                  asChild
                >
                  <Link
                    to="/knowledge/$kbId/documents/$docId"
                    params={{ kbId, docId: doc.id }}
                    aria-label="查看分段"
                  >
                    <LayoutList className="size-4" />
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent>查看分段</TooltipContent>
            </Tooltip>
          )}

          {canPreview && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground size-7"
                  onClick={onPreview}
                  aria-label="预览"
                >
                  <Eye className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>预览</TooltipContent>
            </Tooltip>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground hover:text-foreground size-7"
                onClick={handleDownload}
                disabled={downloading}
                aria-label="下载"
              >
                <Download className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>下载</TooltipContent>
          </Tooltip>

          {parseLabel && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-brand hover:text-brand-hover size-7"
                  onClick={handleParse}
                  disabled={triggering}
                  aria-label={parseLabel}
                >
                  <ScanText className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{parseLabel}</TooltipContent>
            </Tooltip>
          )}

          {indexLabel && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-brand hover:text-brand-hover size-7"
                  onClick={() => runTrigger('index')}
                  disabled={triggering}
                  aria-label={indexLabel}
                >
                  <Sparkles className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{indexLabel}</TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* ⋯ 菜单：只剩破坏性操作（删除） */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground size-7 shrink-0"
            >
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              variant="destructive"
              onSelect={(e) => {
                e.preventDefault()
                setConfirmOpen(true)
              }}
            >
              <Trash2 className="size-4" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <AlertDialog open={reparseConfirmOpen} onOpenChange={setReparseConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>重新解析「{doc.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              将清除该文档现有的段落和索引，知识库将检索不到它的内容。{REPARSE_CONSEQUENCE}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={triggering}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={triggering}
              onClick={(e) => {
                e.preventDefault()
                runTrigger('parse')
              }}
            >
              {triggering ? '提交中…' : '重新解析'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除文档「{doc.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。文档的段落与索引将一并清除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              variant="destructive"
            >
              {deleting ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// ---------- helpers ----------

/** 文本类文件才暴露「预览」入口；PDF / docx 等二进制等 v2 多格式预览片做。 */
function isPreviewable(name: string): boolean {
  const lower = name.toLowerCase()
  return lower.endsWith('.md') || lower.endsWith('.txt')
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
