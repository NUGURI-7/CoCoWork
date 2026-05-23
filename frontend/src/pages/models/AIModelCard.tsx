import { CircleCheck, CircleX, Settings } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { AIModel } from '@/types'

/** 模型类型 → 标签 */
const modelTypeLabel: Record<string, string> = {
  chat: '对话',
  embedding: '向量',
  rerank: '重排序',
}

/** 模型类型 → 颜色 */
const modelTypeBadgeVariant: Record<string, string> = {
  chat: 'bg-blue-50 text-blue-700 border-blue-200',
  embedding: 'bg-amber-50 text-amber-700 border-amber-200',
  rerank: 'bg-violet-50 text-violet-700 border-violet-200',
}

export function AIModelCard({ model }: { model: AIModel }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span
            className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${modelTypeBadgeVariant[model.model_type] ?? ''}`}
          >
            {modelTypeLabel[model.model_type] ?? model.model_type}
          </span>
          <div className="flex items-center gap-1">
            {model.is_enabled ? (
              <CircleCheck className="size-3.5 text-success" />
            ) : (
              <CircleX className="size-3.5 text-muted-foreground" />
            )}
            <Button variant="ghost" size="icon" className="size-6">
              <Settings className="size-3" />
            </Button>
          </div>
        </div>
        <div>
          <h4 className="text-sm font-medium leading-none">{model.display_name}</h4>
          <p className="text-muted-foreground mt-1 font-mono text-xs">
            {model.model_name}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
