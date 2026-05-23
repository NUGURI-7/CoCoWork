import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ProviderCard } from './ProviderCard'
import { mockProviders } from './mock'

/** /models — Provider 卡片网格页 */
export default function ModelsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">模型管理</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            管理供应商凭证及其下属模型
          </p>
        </div>
        <Button size="sm">
          <Plus className="size-4" />
          添加供应商
        </Button>
      </div>

      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}
      >
        {mockProviders.map((p) => (
          <ProviderCard key={p.id} provider={p} />
        ))}
      </div>
    </div>
  )
}
