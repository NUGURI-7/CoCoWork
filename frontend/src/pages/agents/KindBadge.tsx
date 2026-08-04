import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { TemplateKind } from '@/types'

interface KindBadgeProps {
  kind: TemplateKind
  className?: string
}

/**
 * 编排形态徽标：Loop（品牌墨绿实底）/ Graph（中性灰实底）。
 *
 * 用于 TemplateCard / AgentCard / ConfigPanel header / CreateAgentDialog 模板小卡，
 * 4 处统一观感。Graph 原来是虚边弱化的，那是 graph 模板还没实装时的占位表达；
 * 现在它是真模板，跟 Loop 平级，只用颜色区分形态、不再暗示「不可用」。
 */
export function KindBadge({ kind, className }: KindBadgeProps) {
  const label = kind === 'loop' ? 'Loop' : 'Graph'
  return (
    <Badge
      variant="outline"
      className={cn(
        'font-medium',
        kind === 'loop'
          ? 'bg-brand-subtle text-brand border-brand-border'
          : 'bg-muted text-muted-foreground',
        className,
      )}
    >
      {label}
    </Badge>
  )
}
