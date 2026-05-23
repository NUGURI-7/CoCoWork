import { useParams } from '@tanstack/react-router'

import { AIModelCard } from './AIModelCard'
import { AvailableModelsCard } from './AvailableModelsCard'
import { ProviderInfoCard } from './ProviderInfoCard'
import { mockAIModels, mockAvailableModels, mockProviders } from './mock'

/** /models/:providerId — Provider 详情页 */
export default function ProviderDetailPage() {
  const { providerId } = useParams({ from: '/_authenticated/models/$providerId' })
  const provider = mockProviders.find((p) => p.id === providerId)

  if (!provider) {
    return (
      <div className="flex h-40 items-center justify-center">
        <p className="text-muted-foreground text-sm">供应商不存在</p>
      </div>
    )
  }

  const availableGroups = mockAvailableModels[providerId] ?? []
  const aiModels = mockAIModels[providerId] ?? []

  return (
    <div className="space-y-6">
      {/* 上栏：左 Provider 信息 / 右 可用模型 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ProviderInfoCard provider={provider} />
        <AvailableModelsCard groups={availableGroups} />
      </div>

      {/* 下栏：已创建模型 */}
      <div>
        <h2 className="mb-4 text-sm font-medium">
          已创建模型
          <span className="text-muted-foreground ml-1.5 font-normal">
            ({aiModels.length})
          </span>
        </h2>
        {aiModels.length === 0 ? (
          <div className="border-border/60 flex items-center justify-center rounded-xl border border-dashed p-12">
            <p className="text-muted-foreground text-sm">
              暂无模型，从右上角可用模型列表中添加
            </p>
          </div>
        ) : (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}
          >
            {aiModels.map((model) => (
              <AIModelCard key={model.id} model={model} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
