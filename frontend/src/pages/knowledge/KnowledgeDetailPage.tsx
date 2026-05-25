import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { BookOpen, ChevronLeft, FlaskConical, Upload } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { ring } from 'ldrs'

import { getKnowledgeBase } from '@/api/knowledge'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { KnowledgeBase } from '@/types'
import { DocumentList } from './DocumentList'
import { KnowledgeSettings } from './KnowledgeSettings'
import { UploadDocumentSheet } from './UploadDocumentSheet'
import { kbStatusMeta, mockDocuments } from './mock'

ring.register()

function TabPlaceholder({
  icon: Icon,
  title,
  desc,
}: {
  icon: LucideIcon
  title: string
  desc: string
}) {
  return (
    <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-center">
      <Icon className="size-8 opacity-40" />
      <p className="text-foreground text-sm font-medium">{title}</p>
      <p className="max-w-xs text-xs">{desc}</p>
    </div>
  )
}

/** /knowledge/$kbId — 知识库详情页（面包屑 + 库信息 header + 3 tab） */
export default function KnowledgeDetailPage() {
  const { kbId } = useParams({ from: '/_authenticated/knowledge/$kbId' })
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(true)
  const [allDocs, setAllDocs] = useState(mockDocuments)
  const [uploadOpen, setUploadOpen] = useState(false)

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getKnowledgeBase(kbId)
      setKb(data)
    } catch {
      // 拦截器已 toast
    } finally {
      setLoading(false)
    }
  }, [kbId])

  useEffect(() => {
    refetch()
  }, [refetch])

  const docs = allDocs.filter((d) => d.kb_id === kbId)

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
        onUploaded={(newDocs) => setAllDocs((prev) => [...newDocs, ...prev])}
      />

      {/* Tabs */}
      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">文档</TabsTrigger>
          <TabsTrigger value="retrieval">检索测试</TabsTrigger>
          <TabsTrigger value="settings">设置</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="mt-4">
          <DocumentList docs={docs} />
        </TabsContent>

        <TabsContent value="retrieval" className="mt-4">
          <TabPlaceholder
            icon={FlaskConical}
            title="检索测试"
            desc="输入查询，预览混合检索命中的片段与分数。待后端检索接口接入后开放。"
          />
        </TabsContent>

        <TabsContent value="settings" className="mt-4">
          <KnowledgeSettings kb={kb} onUpdated={setKb} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
