import { useEffect, useState } from 'react'
import { Download, ExternalLink } from 'lucide-react'

import { getArtifactDownloadUrl } from '@/api/artifact'
import { ArtifactPreviewDialog } from '@/components/chat/ArtifactPreviewDialog'
import {
  formatSize,
  iconFor,
  previewKindOf,
  useArtifactActions,
} from '@/components/chat/artifact-actions'
import { cn } from '@/lib/utils'
import type { Artifact } from '@/types'

/**
 * 沙箱产物卡片 —— agent 这一轮交付出来的一个文件。
 *
 * 三个动作：
 * - 点卡片主体 → 站内浮层预览；类型不支持预览时退回新标签页打开
 * - 点外链图标 → 新标签页打开（inline）
 * - 点下载图标 → 存到本地（attachment）
 *
 * 动作与图标 / 体积格式化都在 artifact-actions 里，与产出物面板共用。
 */
export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  if (artifact.content_type.startsWith('audio/')) {
    return <AudioArtifactCard artifact={artifact} />
  }
  return <FileArtifactCard artifact={artifact} />
}

/** 音频产物：卡片里直接试听，右侧下载。播放地址进卡片时换一次。 */
function AudioArtifactCard({ artifact }: { artifact: Artifact }) {
  const { download } = useArtifactActions(artifact.id)
  const [src, setSrc] = useState<string | null>(null)
  const Icon = iconFor(artifact.content_type)

  useEffect(() => {
    let cancelled = false
    getArtifactDownloadUrl(artifact.id, 'inline')
      .then((url) => {
        if (!cancelled) setSrc(url)
      })
      .catch(() => {
        // 拦截器已 toast；拿不到地址时只剩下载按钮
      })
    return () => {
      cancelled = true
    }
  }, [artifact.id])

  return (
    <div className="border-border bg-muted/40 flex w-full max-w-md flex-col gap-2 rounded-lg border px-3 py-2.5">
      <div className="flex items-center gap-3">
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
        <button
          type="button"
          aria-label="下载"
          title="下载"
          onClick={download}
          className={cn(
            'text-muted-foreground hover:text-foreground hover:bg-background',
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors',
          )}
        >
          <Download size={16} />
        </button>
      </div>
      {src && <audio controls preload="metadata" src={src} className="h-9 w-full" />}
    </div>
  )
}

function FileArtifactCard({ artifact }: { artifact: Artifact }) {
  const { busy, open, download } = useArtifactActions(artifact.id)
  const [previewing, setPreviewing] = useState(false)
  const Icon = iconFor(artifact.content_type)

  const canPreview = !!previewKindOf(artifact.filename, artifact.content_type)

  return (
    <>
    <button
      type="button"
      onClick={() => (canPreview ? setPreviewing(true) : open())}
      disabled={busy}
      title={`${artifact.filename} —— 点击${canPreview ? '预览' : '在新标签页打开'}`}
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
        aria-label="在新标签页打开"
        onClick={(e) => {
          e.stopPropagation() // 别顺带触发外层的「预览」
          open()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') open()
        }}
        className={cn(
          'text-muted-foreground hover:text-foreground hover:bg-background',
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors',
        )}
      >
        <ExternalLink size={16} />
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

    {previewing && (
      <ArtifactPreviewDialog
        artifact={artifact}
        onClose={() => setPreviewing(false)}
      />
    )}
    </>
  )
}
