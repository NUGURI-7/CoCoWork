import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import { sourceMeta, type Tool } from './mock'

interface ToolCardProps {
  tool: Tool
  onToggle: (enabled: boolean) => void
}

export function ToolCard({ tool, onToggle }: ToolCardProps) {
  const Icon = tool.icon
  return (
    <div
      className={cn(
        'flex min-h-[150px] flex-col gap-3 rounded-xl border p-6 transition-opacity',
        !tool.enabled && 'opacity-65',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="bg-muted flex size-10 shrink-0 items-center justify-center rounded-lg">
            <Icon className="text-muted-foreground size-6" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-base font-medium">{tool.name}</div>
            <div className="mt-0.5 flex items-center gap-1.5">
              <Badge variant="outline" className="px-1.5 py-0 text-[11px] font-normal">
                {sourceMeta[tool.source].label}
              </Badge>
              {tool.server && (
                <span className="text-muted-foreground truncate text-xs">
                  {tool.server}
                </span>
              )}
            </div>
          </div>
        </div>
        <Switch checked={tool.enabled} onCheckedChange={onToggle} />
      </div>

      <p className="text-muted-foreground line-clamp-2 text-sm leading-relaxed">
        {tool.description}
      </p>
    </div>
  )
}
