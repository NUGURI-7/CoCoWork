import { useNavigate } from '@tanstack/react-router'
import { Cloud, CircleCheck, CircleX, Layers } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { Provider } from '@/types'

/** Provider 类型 → 中文标签 */
const providerTypeLabel: Record<string, string> = {
  openai: 'OpenAI',
  dashscope: '阿里云百炼',
  siliconflow: '硅基流动',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  custom: '自定义',
}

/** Provider 类型 → 品牌色 */
const providerDotColor: Record<string, string> = {
  openai: 'bg-emerald-500',
  dashscope: 'bg-orange-500',
  siliconflow: 'bg-violet-500',
  deepseek: 'bg-blue-500',
  anthropic: 'bg-amber-600',
  custom: 'bg-gray-400',
}

export function ProviderCard({ provider }: { provider: Provider }) {
  const navigate = useNavigate()
  const openTab = useWorkspaceTabsStore((s) => s.open)

  function handleClick() {
    openTab({
      path: `/models/${provider.id}`,
      title: provider.name,
      icon: Cloud,
    })
    navigate({ to: '/models/$providerId', params: { providerId: provider.id } })
  }

  return (
    <Card
      className="cursor-pointer border-transparent ring ring-border/50 transition-all hover:ring-foreground/15 hover:shadow-md"
      onClick={handleClick}
    >
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1.5 text-xs">
            <span
              className={`inline-block size-2 rounded-full ${providerDotColor[provider.provider_type] ?? 'bg-gray-400'}`}
            />
            {providerTypeLabel[provider.provider_type] ?? provider.provider_type}
          </span>
          {provider.is_enabled ? (
            <CircleCheck className="size-4 text-success" />
          ) : (
            <CircleX className="size-4 text-muted-foreground" />
          )}
        </div>
        <div>
          <h3 className="text-sm font-medium leading-none">{provider.name}</h3>
          <p className="text-muted-foreground mt-1.5 line-clamp-2 text-xs">
            {provider.description || ' '}
          </p>
        </div>
        <div className="flex h-5 items-center justify-between">
          <div>
            {provider.is_global && (
              <span className="bg-secondary text-secondary-foreground rounded px-1.5 py-0.5 text-[10px] font-medium">
                全局
              </span>
            )}
          </div>
          <span className="text-muted-foreground/60 flex items-center gap-1 text-[10px]">
            <Layers className="size-3" />
            {provider.model_count ?? 0} 个模型
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
