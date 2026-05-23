import { Loader2, Plus, RefreshCw } from 'lucide-react'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AvailableModelGroup } from '@/types'

/** 模型类型 → 图标色 */
const typeColor: Record<string, string> = {
  chat: 'bg-blue-500',
  embedding: 'bg-amber-500',
  rerank: 'bg-violet-500',
}

interface AvailableModelsCardProps {
  groups: AvailableModelGroup[]
  loading?: boolean
  onRefresh?: () => void
  onAdd?: (modelName: string, modelType: string) => void
}

export function AvailableModelsCard({
  groups,
  loading,
  onRefresh,
  onAdd,
}: AvailableModelsCardProps) {
  const totalCount = groups.reduce((sum, g) => sum + g.models.length, 0)

  return (
    <Card className="flex flex-col py-4">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">
          可用模型
          <span className="text-muted-foreground ml-1.5 text-sm font-normal">
            ({totalCount})
          </span>
        </CardTitle>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          disabled={loading}
          onClick={onRefresh}
        >
          {loading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
        </Button>
      </CardHeader>
      <CardContent className="h-44 overflow-y-auto">
        {groups.length === 0 ? (
          <p className="text-muted-foreground py-6 text-center text-sm">
            暂无可用模型
          </p>
        ) : (
          <Accordion type="multiple" defaultValue={groups.map((g) => g.type)}>
            {groups.map((group) => (
              <AccordionItem key={group.type} value={group.type}>
                <AccordionTrigger className="py-2 text-sm">
                  <span className="flex items-center gap-2">
                    <span className={`inline-block size-2 rounded-full ${typeColor[group.type] ?? 'bg-gray-400'}`} />
                    {group.label}
                    <span className="text-muted-foreground text-xs">
                      {group.models.length}
                    </span>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <ul className="space-y-0.5">
                    {group.models.map((model) => (
                      <li
                        key={model.model_name}
                        className="hover:bg-muted/50 group/item flex items-center justify-between rounded-md px-2 py-1.5"
                      >
                        <span className="truncate font-mono text-xs">
                          {model.model_name}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-6 opacity-0 transition-opacity group-hover/item:opacity-100"
                          onClick={() => onAdd?.(model.model_name, group.type)}
                        >
                          <Plus className="size-3.5" />
                        </Button>
                      </li>
                    ))}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </CardContent>
    </Card>
  )
}
