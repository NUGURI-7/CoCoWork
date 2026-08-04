import { Bot, Workflow, type LucideIcon } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import type { Template, TemplateKind } from '@/types'
import { KindBadge } from './KindBadge'

/**
 * 形态 → 图标。图标不由后端下发 —— 它是纯展示选择，让后端替前端决定长什么样
 * 是错位；而形态只有两种，映射写死即可。
 */
const formIcon: Record<TemplateKind, LucideIcon> = {
  loop: Bot,
  graph: Workflow,
}

export function templateIcon(form: TemplateKind) {
  return formIcon[form]
}

interface TemplateCardProps {
  template: Template
  onClick?: (template: Template) => void
}

export function TemplateCard({ template, onClick }: TemplateCardProps) {
  const Icon = templateIcon(template.form)

  return (
    <Card
      className="card-interactive w-56 shrink-0 gap-0 py-0"
      onClick={() => onClick?.(template)}
    >
      <CardContent className="flex h-full flex-col gap-2.5 p-4">
        <Icon className="text-brand size-5" />
        <h4 className="font-medium leading-tight">{template.name}</h4>
        <p className="text-muted-foreground line-clamp-2 flex-1 text-xs leading-relaxed">
          {template.description}
        </p>
        <KindBadge kind={template.form} className="mt-1 self-start" />
      </CardContent>
    </Card>
  )
}
