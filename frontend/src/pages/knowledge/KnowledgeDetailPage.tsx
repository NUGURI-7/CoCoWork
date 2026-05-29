import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { BookOpen, ChevronLeft, Upload } from 'lucide-react'
import { ring } from 'ldrs'

import { getKnowledgeBase, listDocuments } from '@/api/knowledge'
import { useTabTitle } from '@/stores/use-tab-sync'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Document, KnowledgeBase } from '@/types'
import { DocumentList } from './DocumentList'
import { KnowledgeSettings } from './KnowledgeSettings'
import { RetrievalTest } from './RetrievalTest'
import { UploadDocumentSheet } from './UploadDocumentSheet'
import { kbStatusMeta } from './mock'

ring.register()

/** /knowledge/$kbId — 知识库详情页（面包屑 + 库信息 header + 3 tab） */
export default function KnowledgeDetailPage() {
  const { kbId } = useParams({ from: '/_authenticated/knowledge/$kbId' })
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(true)
  const [docs, setDocs] = useState<Document[]>([])
  const [uploadOpen, setUploadOpen] = useState(false)

  const refetchDocs = useCallback(async () => {
    try {
      const data = await listDocuments(kbId)
      setDocs(data)
    } catch {
      // 拦截器已 toast
    }
  }, [kbId])

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const [kbData] = await Promise.all([getKnowledgeBase(kbId), refetchDocs()])
      setKb(kbData)
    } catch {
      // 拦截器已 toast
    } finally {
      setLoading(false)
    }
  }, [kbId, refetchDocs])

  useEffect(() => {
    refetch()
  }, [refetch])

  // 任一文档处于 processing → 1.5s 后再 refetch，循环直到全部脱离 processing
  useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === 'processing')
    if (!hasProcessing) return
    const timer = setTimeout(refetchDocs, 1500)
    return () => clearTimeout(timer)
  }, [docs, refetchDocs])

  useTabTitle(`/knowledge/${kbId}`, kb?.name)

  if (loading || !kb) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  const s = kbStatusMeta[kb.status]

  return (
    <div className="space-y-6">
      {/* 面包屑（回列表） */}
      <Link
        to="/knowledge"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors"
      >
        <ChevronLeft className="size-4" />
        知识库
      </Link>

      {/* 库信息 header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="bg-brand-subtle flex size-12 shrink-0 items-center justify-center rounded-xl">
            <BookOpen className="text-brand size-6" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-xl font-semibold">{kb.name}</h1>
              <span className="text-muted-foreground flex shrink-0 items-center gap-1.5 text-xs">
                <span className={cn('size-2 rounded-full', s.dot, s.pulse && 'animate-pulse')} />
                {s.label}
              </span>
            </div>
            <p className="text-muted-foreground mt-1 text-sm">{kb.description}</p>
            <p className="text-muted-foreground mt-1.5 text-xs">
              {kb.doc_count} 文档 · {kb.chunk_count.toLocaleString()} chunks · {kb.embedding_model_name}
            </p>
          </div>
        </div>
        <Button size="sm" className="shrink-0" onClick={() => setUploadOpen(true)}>
          <Upload className="size-4" />
          上传文档
        </Button>
      </div>

      <UploadDocumentSheet
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        kbId={kbId}
        onUploaded={refetchDocs}
      />

      {/* Tabs */}
      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">文档</TabsTrigger>
          <TabsTrigger value="retrieval">检索测试</TabsTrigger>
          <TabsTrigger value="settings">设置</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="mt-4">
          <DocumentList
            kbId={kbId}
            docs={docs}
            onDeleted={refetchDocs}
            onProcessed={(docId) =>
              setDocs((prev) =>
                prev.map((d) =>
                  d.id === docId ? { ...d, status: 'processing', stage: 'parsing' } : d,
                ),
              )
            }
          />
        </TabsContent>

        <TabsContent value="retrieval" className="mt-4">
          <RetrievalTest kbId={kbId} />
        </TabsContent>

        <TabsContent value="settings" className="mt-4">
          <KnowledgeSettings kb={kb} onUpdated={setKb} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
