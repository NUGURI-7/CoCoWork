import { useState } from 'react'
import { BookOpen, Download, KeyRound, Package, Trash2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { toast } from 'sonner'

import { deleteSkill, getSkillDownloadUrl } from '@/api/skill'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { triggerDownload } from '@/lib/download'
import type { Skill, SkillSource } from '@/types'

/** 来源 → 图标 + 标签（后端不下发图标，前端按来源统一给） */
const SOURCE_META: Record<SkillSource, { label: string; icon: LucideIcon }> = {
  builtin: { label: '内置', icon: BookOpen },
  user: { label: '上传', icon: Package },
}

/**
 * Skill 卡
 *
 * 与 ToolCard 的两处刻意差异：
 * - 标题用 `name` 而非中文展示名 —— skill 的 name 是规范强制的小写连字符标识
 *   （`svg-chart`），它同时也是进 system prompt 给模型看的那个名字。另造一个中文名
 *   会和模型看到的对不上，排查「模型为什么不用这个 skill」时会误导。
 * - 没有「有副作用」标记，改为「需要 key」—— skill 的危险来自它跑的脚本，那由沙箱兜；
 *   用户在这一层真正需要知道的是「用之前得先配凭据」。
 *
 * 下载与删除都只对上传的那批开放：内置 skill 随代码分发、表里根本没有行，
 * 既没有可删之物，也没有原始包可导出。
 */
export function SkillCard({
  skill,
  onDeleted,
}: {
  skill: Skill
  onDeleted?: () => void
}) {
  const meta = SOURCE_META[skill.source_type]
  const Icon = meta.icon
  const needsKey = skill.required_env.length > 0
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [downloading, setDownloading] = useState(false)

  /** URL 不预先持有，点了才向后端换 —— 每次点击都过一遍归属校验，链接也不长期有效。 */
  async function handleDownload() {
    if (!skill.id || downloading) return
    setDownloading(true)
    try {
      triggerDownload(await getSkillDownloadUrl(skill.id), `${skill.name}.zip`)
    } catch {
      // 拦截器已 toast
    } finally {
      setDownloading(false)
    }
  }

  async function handleDelete() {
    if (!skill.id) return
    setDeleting(true)
    try {
      await deleteSkill(skill.id)
      toast.success(`已删除 ${skill.name}`)
      setConfirmOpen(false)
      onDeleted?.()
    } catch {
      toast.error('删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="group flex min-h-[150px] flex-col gap-3 rounded-xl border p-6">
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

        {skill.id && (
          <div className="ml-auto flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            <Button
              variant="ghost"
              size="icon"
              aria-label="下载"
              title="下载原始包"
              disabled={downloading}
              className="text-muted-foreground hover:text-foreground size-8"
              onClick={() => void handleDownload()}
            >
              <Download className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="删除"
              className="text-muted-foreground hover:text-destructive size-8"
              onClick={() => setConfirmOpen(true)}
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
        )}
      </div>

      <p className="text-muted-foreground line-clamp-3 text-sm leading-relaxed">
        {skill.description}
      </p>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除 skill「{skill.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销，包也会一并从存储中删除。挂载了它的 Agent 将失去这项技能。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault()
                void handleDelete()
              }}
            >
              {deleting ? '删除中...' : '删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
