import { useCallback, useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { ring } from 'ldrs'

import { listKnowledgeBases } from '@/api/knowledge'
import { Button } from '@/components/ui/button'
import type { KnowledgeBase } from '@/types'
import { CreateKnowledgeDialog } from './CreateKnowledgeDialog'
import { KnowledgeCard } from './KnowledgeCard'
import { KnowledgeFolderTree } from './KnowledgeFolderTree'

ring.register()

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex-1 px-5 py-3">
      <div className="font-serif text-2xl leading-none">{value}</div>
      <div className="text-muted-foreground mt-1 text-xs">{label}</div>
    </div>
  )
}

/** /knowledge — 知识库列表页（三带布局 + 左侧目录树预留壳） */
export default function KnowledgePage() {
  const [items, setItems] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listKnowledgeBases()
      setItems(data)
    } catch {
      // 全局拦截器已 toast；保持空列表
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  const totalDocs = items.reduce((sum, k) => sum + k.doc_count, 0)
  const totalChunks = items.reduce((sum, k) => sum + k.chunk_count, 0)

  return (
    <div className="space-y-6">
      {/* ① Header 带（横跨整宽） */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">知识库</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            管理你的文档库与检索配置
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          新建知识库
        </Button>
      </div>

      {/* 两栏容器：左目录树（预留隐藏） | 右内容区 */}
      <div className="flex gap-6">
        <KnowledgeFolderTree />

        <div className="min-w-0 flex-1 space-y-5">
          {loading ? (
            <div className="flex min-h-[60vh] items-center justify-center">
              <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
            </div>
          ) : (
            <>
              {/* 范围标题 / 面包屑位（预留，将来显示 全部 ▸ 产品 ▸ …） */}
              <div className="text-muted-foreground text-sm">
                全部知识库 ·{' '}
                <span className="text-foreground font-medium">{items.length}</span>
              </div>

              {/* ② 概览统计带 */}
              <div className="flex divide-x rounded-lg border">
                <Stat label="知识库" value={items.length} />
                <Stat label="文档" value={totalDocs} />
                <Stat label="chunks" value={totalChunks.toLocaleString()} />
              </div>

              {/* ③ 卡片网格 + 新建卡 */}
              <div
                className="grid gap-4"
                style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}
              >
                {items.map((kb) => (
                  <KnowledgeCard key={kb.id} kb={kb} onDeleted={refetch} />
                ))}

                {/* 新建虚线卡 */}
                <button
                  type="button"
                  onClick={() => setCreateOpen(true)}
                  className="group border-border/70 text-muted-foreground hover:border-brand hover:text-brand flex min-h-[168px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed transition-colors"
                >
                  <Plus className="size-5" />
                  <span className="text-sm font-medium">新建知识库</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <CreateKnowledgeDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={refetch}
      />
    </div>
  )
}
