import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { ring } from 'ldrs'

import { listCatalog, listModelsByProvider } from '@/api/model'
import { get } from '@/request'
import type {
  AIModel,
  AvailableModelGroup,
  CatalogItem,
  ModelType,
  Provider,
} from '@/types'
import { AIModelCard } from './AIModelCard'
import { AvailableModelsCard } from './AvailableModelsCard'
import { CreateModelDialog } from './CreateModelDialog'
import { ProviderInfoCard } from './ProviderInfoCard'

ring.register()

const modelTypeLabel: Record<string, string> = {
  chat: '对话',
  embedding: '向量',
  rerank: '重排序',
  vision: '视觉',
  tts: '语音合成',
  stt: '语音识别',
  image: '图像',
  multimodal: '多模态',
}

/** /models/:providerId — Provider 详情页 */
export default function ProviderDetailPage() {
  const { providerId } = useParams({ from: '/_authenticated/models/$providerId' })

  const [provider, setProvider] = useState<Provider | null>(null)
  const [models, setModels] = useState<AIModel[]>([])
  const [catalog, setCatalog] = useState<CatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [catalogLoading, setCatalogLoading] = useState(false)

  const [createDialog, setCreateDialog] = useState<{
    open: boolean
    modelName: string
    modelType: ModelType
  }>({ open: false, modelName: '', modelType: 'chat' })

  const refetchModels = useCallback(async () => {
    try {
      const data = await listModelsByProvider(providerId)
      setModels(data)
    } catch {
      // 拦截器已 toast
    }
  }, [providerId])

  const refetchCatalog = useCallback(
    async (providerType: Provider['provider_type']) => {
      setCatalogLoading(true)
      try {
        const data = await listCatalog(providerType)
        setCatalog(data)
      } catch {
        // 拦截器已 toast
      } finally {
        setCatalogLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    let cancelled = false
    async function loadAll() {
      setLoading(true)
      try {
        const p = await get<Provider>(`/providers/${providerId}`)
        if (cancelled) return
        setProvider(p)
        await Promise.all([refetchModels(), refetchCatalog(p.provider_type)])
      } catch {
        // 拦截器已 toast；保持 provider=null 显示 fallback
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadAll()
    return () => {
      cancelled = true
    }
  }, [providerId, refetchModels, refetchCatalog])

  /** Catalog 平铺数据 → AvailableModelsCard 期望的分组结构 */
  const availableGroups = useMemo<AvailableModelGroup[]>(() => {
    const byType = new Map<ModelType, CatalogItem[]>()
    for (const item of catalog) {
      const list = byType.get(item.model_type) ?? []
      list.push(item)
      byType.set(item.model_type, list)
    }
    return Array.from(byType, ([type, items]) => ({
      type,
      label: modelTypeLabel[type] ?? type,
      models: items.map((i) => ({ model_name: i.model_id, model_type: i.model_type })),
    }))
  }, [catalog])

  function handleAddModel(modelName: string, modelType: string) {
    setCreateDialog({ open: true, modelName, modelType: modelType as ModelType })
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  if (!provider) {
    return (
      <div className="flex h-40 items-center justify-center">
        <p className="text-muted-foreground text-sm">供应商不存在</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 上栏：左 Provider 信息 / 右 可用模型 */}
      <div className="grid grid-cols-2 gap-6">
        <ProviderInfoCard provider={provider} />
        <AvailableModelsCard
          groups={availableGroups}
          loading={catalogLoading}
          onRefresh={() => refetchCatalog(provider.provider_type)}
          onAdd={handleAddModel}
        />
      </div>

      {/* 下栏：已创建模型 */}
      <div>
        <h2 className="mb-4 text-sm font-medium">
          已创建模型
          <span className="text-muted-foreground ml-1.5 font-normal">
            ({models.length})
          </span>
        </h2>
        {models.length === 0 ? (
          <div className="border-border/60 flex items-center justify-center rounded-xl border border-dashed p-12">
            <p className="text-muted-foreground text-sm">
              暂无模型，从右上角可用模型列表中添加
            </p>
          </div>
        ) : (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}
          >
            {models.map((model) => (
              <AIModelCard
                key={model.id}
                providerId={providerId}
                model={model}
                onDeleted={refetchModels}
              />
            ))}
          </div>
        )}
      </div>

      <CreateModelDialog
        open={createDialog.open}
        onOpenChange={(v) => setCreateDialog((prev) => ({ ...prev, open: v }))}
        providerId={providerId}
        modelName={createDialog.modelName}
        modelType={createDialog.modelType}
        onCreated={refetchModels}
      />
    </div>
  )
}
