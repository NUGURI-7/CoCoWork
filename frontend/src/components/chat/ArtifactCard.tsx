import { Download } from 'lucide-react'

import {
  formatSize,
  iconFor,
  useArtifactActions,
} from '@/components/chat/artifact-actions'
import { cn } from '@/lib/utils'
import type { Artifact } from '@/types'

/**
 * 沙箱产物卡片 —— agent 这一轮交付出来的一个文件。
 *
 * 两个动作，各换各的链接：
 * - 点卡片主体 → 新标签页打开看（inline，浏览器直接渲染 SVG / 图片 / 文本）
 * - 点下载图标 → 存到本地（attachment）
 *
 * 动作与图标 / 体积格式化都在 artifact-actions 里，与产出物面板共用。
 *
 * 站内预览（不跳出对话）挂账未做，见 issues/003 —— 那一刀只是把同一个 URL
 * 换个容器渲染，不影响这里的形态。
 */
export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const { busy, open, download } = useArtifactActions(artifact.id)
  const Icon = iconFor(artifact.content_type)

  return (
    <button
      type="button"
      onClick={open}
      disabled={busy}
      title={`${artifact.filename} —— 点击在新标签页打开`}
      className={cn(
        'group/artifact border-border bg-muted/40 flex w-full max-w-md items-center gap-3',
        'rounded-lg border px-3 py-2.5 text-left transition-colors',
        'hover:bg-muted disabled:opacity-60',
      )}
    >
      <span className="bg-background text-muted-foreground flex h-9 w-9 shrink-0 items-center justify-center rounded-md">
        <Icon size={18} />
      </span>

      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-foreground truncate text-sm font-medium">
          {artifact.filename}
        </span>
        <span className="text-muted-foreground text-xs">
          {formatSize(artifact.size)}
        </span>
      </span>

      <span
        role="button"
        tabIndex={0}
        aria-label="下载"
        onClick={download}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') download()
        }}
        className={cn(
          'text-muted-foreground hover:text-foreground hover:bg-background',
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors',
        )}
      >
        <Download size={16} />
      </span>
    </button>
  )
}
