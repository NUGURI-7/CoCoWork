import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ChevronLeft, ChevronsDownUp, ChevronsUpDown, FileText, Inbox, Sparkles } from 'lucide-react'
import { ring } from 'ldrs'
import { toast } from 'sonner'

import {
  getDocument,
  getKnowledgeBase,
  listParagraphsPaginated,
  triggerIndexDocument,
} from '@/api/knowledge'
import { DataPagination } from '@/components/data-pagination'
import { Button } from '@/components/ui/button'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Document, KnowledgeBase, PageData, Paragraph } from '@/types'
import { ParagraphCard } from './ParagraphCard'

const PAGE_SIZE = 20

/** 处理中轮询文档状态的间隔，与知识库详情页文档列表一致 */
const POLL_INTERVAL_MS = 1500

/** 空分页结果占位（初始 state / 错误 fallback） */
const EMPTY_PAGE: PageData<Paragraph> = {
  total: 0,
  records: [],
  current_page: 1,
  page_size: PAGE_SIZE,
  total_pages: 0,
}

ring.register()

/**
 * /knowledge/$kbId/documents/$docId — 文档分段页。
 *
 * 只读展示文档被切成了哪些段，用来核对切分质量：标题链对不对、段是不是被腰斩、
 * 有没有只剩一行标题的空段。编辑能力后续版本再加。
 *
 * 文档待建索引（parsed）时顶部给「建索引」按钮：审完段落就地触发，不必退回列表。
 * 文档处理中时轮询其状态，结束后刷新统计与段列表（子块数随建索引变化）。
 *
 * 展开态放在页面级而不是卡片内部：顶部的「全部展开 / 全部收起」要能一把推平所有卡片，
 * 状态散在各卡片里就同步不了。每次取到新一页都重置为全部展开。
 */
export default function DocumentParagraphsPage() {
  const { kbId, docId } = useParams({
    from: '/_authenticated/knowledge/$kbId_/documents/$docId',
  })

  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [doc, setDoc] = useState<Document | null>(null)
  const [pageData, setPageData] = useState<PageData<Paragraph>>(EMPTY_PAGE)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [triggering, setTriggering] = useState(false)

  // header 用的库 / 文档信息只在 id 变化时取一次，翻页不重复请求
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [kbData, docData] = await Promise.all([
          getKnowledgeBase(kbId),
          getDocument(kbId, docId),
        ])
        if (cancelled) return
        setKb(kbData)
        setDoc(docData)
      } catch {
        // 拦截器已 toast
      }
    })()
    return () => {
      cancelled = true
    }
  }, [kbId, docId])

  const fetchParagraphs = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listParagraphsPaginated(kbId, docId, {
        page,
        page_size: PAGE_SIZE,
      })
      setPageData(data)
      setExpandedIds(new Set(data.records.map((p) => p.id))) // 换页 = 新内容，回到默认展开
    } catch {
      setPageData(EMPTY_PAGE)
    } finally {
      setLoading(false)
    }
  }, [kbId, docId, page])

  useEffect(() => {
    fetchParagraphs()
  }, [fetchParagraphs])

  // 处理中 → 定时取文档状态，直到脱离 processing；结束时刷新段列表并提示结果
  useEffect(() => {
    if (doc?.status !== 'processing') return
    const timer = setTimeout(async () => {
      try {
        const next = await getDocument(kbId, docId)
        setDoc(next)
        if (next.status === 'processing') return
        fetchParagraphs()
        if (next.status === 'completed') toast.success('建索引完成')
        else if (next.status === 'failed') toast.error(next.error_message || '处理失败')
      } catch {
        // 拦截器已 toast
      }
    }, POLL_INTERVAL_MS)
    return () => clearTimeout(timer)
  }, [doc, kbId, docId, fetchParagraphs])

  async function handleIndex() {
    if (triggering) return
    setTriggering(true)
    try {
      setDoc(await triggerIndexDocument(kbId, docId))
      toast.success('已触发建索引')
    } catch {
      // 拦截器已 toast
    } finally {
      setTriggering(false)
    }
  }

  useTabTitle(`/knowledge/${kbId}/documents/${docId}`, doc?.name)

  const allExpanded = useMemo(
    () => pageData.records.length > 0 && expandedIds.size === pageData.records.length,
    [pageData.records.length, expandedIds.size],
  )

  function toggleOne(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setExpandedIds((prev) =>
      prev.size === pageData.records.length
        ? new Set()
        : new Set(pageData.records.map((p) => p.id)),
    )
  }

  return (
    // 阅读型页面：整列限宽居中（约 50 字一行），留白落在页面两侧而不是卡片里
    <div className="mx-auto max-w-4xl space-y-6">
      {/* 面包屑：知识库列表 / 本库 / 当前文档 */}
      <div className="text-muted-foreground flex min-w-0 items-center gap-1 text-sm">
        <Link
          to="/knowledge"
          className="hover:text-foreground inline-flex shrink-0 items-center gap-1 transition-colors"
        >
          <ChevronLeft className="size-4" />
          知识库
        </Link>
        <span className="shrink-0">/</span>
        <Link
          to="/knowledge/$kbId"
          params={{ kbId }}
          className="hover:text-foreground max-w-[12rem] truncate transition-colors"
        >
          {kb?.name ?? '…'}
        </Link>
        <span className="shrink-0">/</span>
        <span className="text-foreground truncate">{doc?.name ?? '…'}</span>
      </div>

      {/* 文档 header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="bg-brand-subtle flex size-12 shrink-0 items-center justify-center rounded-xl">
            <FileText className="text-brand size-6" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold">{doc?.name ?? '文档分段'}</h1>
            <p className="text-muted-foreground mt-1.5 text-xs">
              {doc
                ? `${doc.paragraph_count} 段 · ${doc.chunk_count.toLocaleString()} chunks · ${doc.char_length.toLocaleString()} 字符`
                : '加载中…'}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {pageData.records.length > 0 && (
            <Button variant="outline" size="sm" onClick={toggleAll}>
              {allExpanded ? (
                <ChevronsDownUp className="size-4" />
              ) : (
                <ChevronsUpDown className="size-4" />
              )}
              {allExpanded ? '全部收起' : '全部展开'}
            </Button>
          )}
          {doc?.status === 'parsed' && (
            <Button size="sm" disabled={triggering} onClick={handleIndex}>
              <Sparkles className="size-4" />
              建索引
            </Button>
          )}
          {doc?.status === 'processing' && (
            <Button size="sm" disabled>
              <l-ring size="14" stroke="2" speed="2" color="currentColor" />
              处理中…
            </Button>
          )}
        </div>
      </div>

      {/* 段列表 */}
      {loading ? (
        <div className="flex min-h-[300px] items-center justify-center">
          <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
        </div>
      ) : pageData.records.length === 0 ? (
        <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-center">
          <Inbox className="size-8 opacity-40" />
          <p className="text-foreground text-sm font-medium">这份文档还没有分段</p>
          <p className="max-w-xs text-xs">
            段是解析时切出来的。回到知识库对这份文档执行「解析」，完成后即可在这里查看切分结果
          </p>
        </div>
      ) : (
        <>
          {/* 浅灰底板衬白卡片，段与段的边界更醒目 */}
          <div className="bg-muted/60 space-y-3 rounded-xl p-3">
            {pageData.records.map((p) => (
              <ParagraphCard
                key={p.id}
                paragraph={p}
                expanded={expandedIds.has(p.id)}
                onToggle={() => toggleOne(p.id)}
              />
            ))}
          </div>
          <DataPagination
            page={pageData.current_page}
            totalPages={pageData.total_pages}
            total={pageData.total}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  )
}
