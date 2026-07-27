import { BookOpen, KeyRound, Package } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { Skill, SkillSource } from '@/types'

/** 来源 → 图标 + 标签（后端不下发图标，前端按来源统一给） */
const SOURCE_META: Record<SkillSource, { label: string; icon: LucideIcon }> = {
  builtin: { label: '内置', icon: BookOpen },
  user: { label: '上传', icon: Package },
}

/**
 * Skill 卡（只读）
 *
 * 与 ToolCard 的两处刻意差异：
 * - 标题用 `name` 而非中文展示名 —— skill 的 name 是规范强制的小写连字符标识
 *   （`svg-chart`），它同时也是进 system prompt 给模型看的那个名字。另造一个中文名
 *   会和模型看到的对不上，排查「模型为什么不用这个 skill」时会误导。
 * - 没有「有副作用」标记，改为「需要 key」—— skill 的危险来自它跑的脚本，那由沙箱兜；
 *   用户在这一层真正需要知道的是「用之前得先配凭据」。
 */
export function SkillCard({ skill }: { skill: Skill }) {
  const meta = SOURCE_META[skill.source_type]
  const Icon = meta.icon
  const needsKey = skill.required_env.length > 0

  return (
    <div className="flex min-h-[150px] flex-col gap-3 rounded-xl border p-6">
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="bg-muted flex size-10 shrink-0 items-center justify-center rounded-lg">
          <Icon className="text-muted-foreground size-6" />
        </div>
        <div className="min-w-0">
          <div className="truncate font-mono text-base font-medium">
            {skill.name}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5">
            <Badge
              variant="outline"
              className="px-1.5 py-0 text-[11px] font-normal"
            >
              {meta.label}
            </Badge>
            {needsKey && (
              <Badge
                variant="outline"
                className="border-warning/40 text-warning gap-1 px-1.5 py-0 text-[11px] font-normal"
                title={skill.required_env.join('、')}
              >
                <KeyRound className="size-3" />
                需要 key
              </Badge>
            )}
          </div>
        </div>
      </div>

      <p className="text-muted-foreground line-clamp-3 text-sm leading-relaxed">
        {skill.description}
      </p>
    </div>
  )
}
