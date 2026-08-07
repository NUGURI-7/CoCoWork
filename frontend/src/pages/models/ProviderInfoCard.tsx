import { useState } from 'react'
import { ExternalLink, Pencil } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Provider } from '@/types'
import { ProviderFormDialog } from './ProviderFormDialog'

/** Provider 类型 → 中文标签 */
const providerTypeLabel: Record<string, string> = {
  openai: 'OpenAI',
  dashscope: '阿里云百炼',
  siliconflow: '硅基流动',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  custom: '自定义',
}

/** 信息行 */
function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-x-3 text-sm">
      <span className="text-muted-foreground w-20 shrink-0">{label}</span>
      <span className="min-w-0 break-all">{children}</span>
    </div>
  )
}

export function ProviderInfoCard({
  provider,
  onUpdated,
}: {
  provider: Provider
  /** 保存成功后让详情页重拉 provider —— 名字 / base_url 都可能变了 */
  onUpdated?: () => void
}) {
  const [editOpen, setEditOpen] = useState(false)

  return (
    <Card className="py-4">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{provider.name}</CardTitle>
        <Button
          variant="ghost"
          size="icon"
          aria-label="编辑供应商"
          className="size-8"
          onClick={() => setEditOpen(true)}
        >
          <Pencil className="size-3.5" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <InfoRow label="类型">
          {providerTypeLabel[provider.provider_type] ?? provider.provider_type}
        </InfoRow>
        <InfoRow label="Base URL">
          <span className="text-muted-foreground inline-flex items-center gap-1 font-mono text-xs">
            {provider.base_url}
            <ExternalLink className="size-3 shrink-0" />
          </span>
        </InfoRow>
        {provider.description && (
          <InfoRow label="描述">
            <span className="text-muted-foreground">{provider.description}</span>
          </InfoRow>
        )}
      </CardContent>

      <ProviderFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        provider={provider}
        onSaved={onUpdated}
      />
    </Card>
  )
}
