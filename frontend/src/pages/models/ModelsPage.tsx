import { useCallback, useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { ring } from 'ldrs'

import { listProviders } from '@/api/model'
import { Button } from '@/components/ui/button'
import type { Provider } from '@/types'
import { ProviderFormDialog } from './ProviderFormDialog'
import { ProviderCard } from './ProviderCard'

ring.register()

/** /models — Provider 卡片网格页 */
export default function ModelsPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listProviders()
      setProviders(data)
    } catch {
      // 全局拦截器已 toast；保持空列表
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">模型管理</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            管理供应商凭证及其下属模型
          </p>
        </div>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="size-4" />
          添加供应商
        </Button>
      </div>

      {loading ? (
        <div className="flex min-h-[60vh] items-center justify-center">
          <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
        </div>
      ) : providers.length === 0 ? (
        <div className="border-border/60 text-muted-foreground flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-sm">
          <p>还没有供应商</p>
          <p className="mt-1 text-xs">点击右上角「添加供应商」开始配置</p>
        </div>
      ) : (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}
        >
          {providers.map((p) => (
            <ProviderCard key={p.id} provider={p} onDeleted={refetch} />
          ))}
        </div>
      )}

      <ProviderFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={refetch}
      />
    </div>
  )
}
