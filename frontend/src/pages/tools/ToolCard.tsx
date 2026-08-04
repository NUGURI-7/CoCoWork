import { AlertTriangle, Code2, Server, Wrench } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { Tool, ToolCategory, ToolSource } from '@/types'

/** 来源 → 图标 + 标签（后端不下发图标，前端按来源统一给） */
const SOURCE_META: Record<ToolSource, { label: string; icon: LucideIcon }> = {
  builtin: { label: '内置', icon: Wrench },
  mcp: { label: 'MCP', icon: Server },
  custom: { label: '自定义', icon: Code2 },
}

/**
 * 能力分类 → 标签。不配图标 —— 来源 badge 也是纯文字，图标只出现在卡片左侧
 * 那个大色块里，一行 badge 里再塞图标会把「有副作用」那个真正需要视觉警示的
 * 标记淹掉。
 */
const CATEGORY_META: Record<ToolCategory, string> = {
  data_source: '数据源',
  utility: '实用工具',
}

/**
 * 工具卡（只读）
 *
 * 工具是平台能力目录、不是可开关的资源 —— 启不启用是按 agent 的
 * （ConfigPanel 勾 `config.builtin_tools`），故这里无开关、纯展示。
 * `dangerous` 标出有副作用的工具（删文件 / 发请求 / 花钱）。
 */
export function ToolCard({ tool }: { tool: Tool }) {
  const meta = SOURCE_META[tool.source_type]
  const Icon = meta.icon
  return (
    <div className="flex min-h-[150px] flex-col gap-3 rounded-xl border p-6">
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="bg-muted flex size-10 shrink-0 items-center justify-center rounded-lg">
          <Icon className="text-muted-foreground size-6" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-base font-medium">{tool.display_name}</div>
          <div className="mt-0.5 flex items-center gap-1.5">
            <Badge variant="outline" className="px-1.5 py-0 text-[11px] font-normal">
              {meta.label}
            </Badge>
            <Badge variant="outline" className="px-1.5 py-0 text-[11px] font-normal">
              {CATEGORY_META[tool.category]}
            </Badge>
            {tool.dangerous && (
              <Badge
                variant="outline"
                className="border-warning/40 text-warning gap-1 px-1.5 py-0 text-[11px] font-normal"
              >
                <AlertTriangle className="size-3" />
                有副作用
              </Badge>
            )}
          </div>
        </div>
      </div>

      <p className="text-muted-foreground line-clamp-2 text-sm leading-relaxed">
        {tool.description}
      </p>
    </div>
  )
}
