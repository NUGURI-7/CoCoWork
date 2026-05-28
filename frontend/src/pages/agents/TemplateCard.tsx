import {
  BarChart3,
  ClipboardCheck,
  Code2,
  Languages,
  LayoutDashboard,
  PenTool,
  Search,
  Sparkles,
  Telescope,
  type LucideIcon,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { Template } from '@/types'

/** 模板 icon 名 → Lucide 组件（mock 数据里只引用名字，组件在前端 map） */
export const iconMap: Record<string, LucideIcon> = {
  Search,
  PenTool,
  ClipboardCheck,
  Telescope,
  Languages,
  BarChart3,
  Code2,
  LayoutDashboard,
}

interface TemplateCardProps {
  template: Template
  onClick?: (template: Template) => void
}

export function TemplateCard({ template, onClick }: TemplateCardProps) {
  const Icon = iconMap[template.icon] ?? Sparkles

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
        <Badge variant="secondary" className="mt-1 self-start text-[10px]">
          {template.behavior_type}
        </Badge>
      </CardContent>
    </Card>
  )
}
