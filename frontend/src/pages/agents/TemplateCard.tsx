import { Bot, Sparkles, Workflow, type LucideIcon } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { Template } from '@/types'
import { KindBadge } from './KindBadge'

/** 模板 icon 名 → Lucide 组件（mock 数据里只引用名字，组件在前端 map） */
export const iconMap: Record<string, LucideIcon> = {
  Bot,
  Workflow,
}

interface TemplateCardProps {
  template: Template
  onClick?: (template: Template) => void
}

export function TemplateCard({ template, onClick }: TemplateCardProps) {
  const Icon = iconMap[template.icon ?? ''] ?? Sparkles
  const disabled = template.disabled === true

  const card = (
    <Card
      className={cn(
        'w-56 shrink-0 gap-0 py-0',
        disabled
          ? 'cursor-not-allowed opacity-60'
          : 'card-interactive',
      )}
      onClick={() => {
        if (disabled) return
        onClick?.(template)
      }}
    >
      <CardContent className="flex h-full flex-col gap-2.5 p-4">
        <Icon className="text-brand size-5" />
        <h4 className="font-medium leading-tight">{template.name}</h4>
        <p className="text-muted-foreground line-clamp-2 flex-1 text-xs leading-relaxed">
          {template.description}
        </p>
        <KindBadge kind={template.kind} className="mt-1 self-start" />
      </CardContent>
    </Card>
  )

  if (!disabled) return card

  return (
    <Tooltip>
      <TooltipTrigger asChild>{card}</TooltipTrigger>
      <TooltipContent>占位 — Graph 形态后端尚未实装</TooltipContent>
    </Tooltip>
  )
}
