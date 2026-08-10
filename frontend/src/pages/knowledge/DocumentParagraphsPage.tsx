import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ChevronLeft, ChevronsDownUp, ChevronsUpDown, FileText, Inbox } from 'lucide-react'
import { ring } from 'ldrs'

import { getDocument, getKnowledgeBase, listParagraphsPaginated } from '@/api/knowledge'
import { DataPagination } from '@/components/data-pagination'
import { Button } from '@/components/ui/button'
import { useTabTitle } from '@/stores/use-tab-sync'
import type { Document, KnowledgeBase, PageData, Paragraph } from '@/types'
import { ParagraphCard } from './ParagraphCard'

const PAGE_SIZE = 20

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
 * 展开态放在页面级而不是卡片内部：顶部的「全部展开 / 全部收起」要能一把推平所有卡片，
 * 状态散在各卡片里就同步不了。翻页时清空，新一页默认全部折叠。
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
      setExpandedIds(new Set()) // 换页 = 新内容，回到默认折叠
    } catch {
      setPageData(EMPTY_PAGE)
    } finally {
      setLoading(false)
    }
  }, [kbId, docId, page])

  useEffect(() => {
    fetchParagraphs()
  }, [fetchParagraphs])

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
    <div className="space-y-6">
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

        {pageData.records.length > 0 && (
          <Button variant="outline" size="sm" className="shrink-0" onClick={toggleAll}>
            {allExpanded ? (
              <ChevronsDownUp className="size-4" />
            ) : (
              <ChevronsUpDown className="size-4" />
            )}
            {allExpanded ? '全部收起' : '全部展开'}
          </Button>
        )}
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
            段是向量化时切出来的。回到知识库对这份文档执行「向量化」，完成后即可在这里查看切分结果
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-2">
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
