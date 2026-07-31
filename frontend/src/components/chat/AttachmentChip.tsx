import { Paperclip, X } from 'lucide-react'

import {
  formatSize,
  iconFor,
  useArtifactActions,
} from '@/components/chat/artifact-actions'
import { cn } from '@/lib/utils'
import type { Artifact } from '@/types'

interface AttachmentChipProps {
  artifact: Artifact
  /** 传了就显示叉号（输入框里待发的那些）；不传 = 已发出去的，只能看不能撤 */
  onRemove?: () => void
}

/**
 * 附件小卡片 —— 用户拖进来的产物引用（后端决策 25）。
 *
 * 两处共用：输入框上方那排「待发送」（带叉号）、消息气泡上方那排「已附上」（不带）。
 * 两处形态必须一样，否则发送前后视觉一跳，用户会以为东西变了。
 *
 * 点击一律是「新标签页打开看」，与 ArtifactCard 同一套动作（每次点都换一个
 * 短期预签名链接，走一遍归属校验）。
 *
 * 比 ArtifactCard 小一号：那是 agent 交付的成果、值得占地方；这是一句话的附件，
 * 是配角。
 */
export function AttachmentChip({ artifact, onRemove }: AttachmentChipProps) {
  const { busy, open } = useArtifactActions(artifact.id)
  // content_type 为空时退回回形针 —— 拿不准类型就别猜一个可能错的图标
  const Icon = artifact.content_type ? iconFor(artifact.content_type) : Paperclip

  return (
    <span
      className={cn(
        'border-border bg-muted/40 inline-flex max-w-[220px] items-center gap-1.5',
        'rounded-lg border py-1 pr-1 pl-2 text-xs transition-colors',
        busy && 'opacity-60',
      )}
    >
      <Icon size={13} className="text-muted-foreground shrink-0" />

      <button
        type="button"
        onClick={open}
        disabled={busy}
        title={`${artifact.filename} —— 点击在新标签页打开`}
        className="min-w-0 flex-1 cursor-pointer text-left"
      >
        <span className="text-foreground block truncate font-medium">
          {artifact.filename}
        </span>
      </button>

      <span className="text-muted-foreground shrink-0 tabular-nums">
        {formatSize(artifact.size)}
      </span>

      {onRemove && (
        <button
          type="button"
          aria-label={`移除 ${artifact.filename}`}
          onClick={onRemove}
          className={cn(
            'text-muted-foreground/60 hover:text-foreground hover:bg-muted',
            'flex size-5 shrink-0 cursor-pointer items-center justify-center rounded transition-colors',
          )}
        >
          <X size={12} />
        </button>
      )}
    </span>
  )
}
