import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { TemplateKind } from '@/types'

interface KindBadgeProps {
  kind: TemplateKind
  className?: string
}

/**
 * 模板分类徽标：Loop（品牌墨绿实底）/ Graph（灰底虚边，弱化占位感）。
 *
 * 用于 TemplateCard / AgentCard / ConfigPanel header / CreateAgentDialog 模板小卡，
 * 4 处统一观感。
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
          : 'bg-muted text-muted-foreground border-dashed',
        className,
      )}
    >
      {label}
    </Badge>
  )
}
