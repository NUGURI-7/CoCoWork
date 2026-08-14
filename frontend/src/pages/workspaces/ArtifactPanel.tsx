import { useCallback, useEffect, useState } from 'react'
import { Download, ExternalLink, FileText, RefreshCw, X } from 'lucide-react'

import { ARTIFACT_PAGE_SIZE, listWorkspaceArtifacts } from '@/api/artifact'
import { ArtifactPreviewDialog } from '@/components/chat/ArtifactPreviewDialog'
import {
  formatArtifactTime,
  formatKind,
  formatSize,
  iconFor,
  previewKindOf,
  useArtifactActions,
} from '@/components/chat/artifact-actions'
import { setArtifactDragData } from '@/components/chat/artifact-drag'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { WorkspaceArtifact } from '@/types'

interface ArtifactPanelProps {
  workspaceId: string
  /**
   * 变一次就重拉一次。上游把 SSE 的 artifacts 帧计数透下来 ——
   * 帧只当「有新产物了」的信号用，数据仍然只从接口来一处。
   */
  refreshKey?: number
  onClose: () => void
}

/** 按对话归组，保持接口给的顺序（已按时间倒序，故新对话在上）。 */
function groupByConversation(items: WorkspaceArtifact[]) {
  const groups: { id: string; name: string; items: WorkspaceArtifact[] }[] = []
  for (const item of items) {
    const last = groups[groups.length - 1]
    if (last?.id === item.conversation_id) {
      last.items.push(item)
      continue
    }
    const existing = groups.find((g) => g.id === item.conversation_id)
    if (existing) {
      existing.items.push(item)
      continue
    }
    groups.push({
      id: item.conversation_id,
      // 对话标题可以为空串（新建时没起名），兜一个默认值，不然分组头是片空白
      name: item.conversation_name || '未命名对话',
      items: [item],
    })
  }
  return groups
}

/**
 * 面板里的一张卡片。舒展而非紧凑：产物是「成果」，值得占地方。
 *
 * **可拖进输入框**（后端决策 25）—— 跨对话也成立，这正是这个功能的意义：
 * 面板本来就把整个工作空间的产出摊在这儿，拖哪条都行。拖走后卡片仍在
 * （effectAllowed=copy，传的是引用不是搬运）。
 */
function ArtifactRow({
  artifact,
  onPreview,
}: {
  artifact: WorkspaceArtifact
  onPreview: (artifact: WorkspaceArtifact) => void
}) {
  const { busy, open, download } = useArtifactActions(artifact.id)
  const Icon = iconFor(artifact.content_type)

  const canPreview = !!previewKindOf(artifact.filename, artifact.content_type)
  const activate = () => (canPreview ? onPreview(artifact) : open())

  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      onDragStart={(e) => setArtifactDragData(e, artifact)}
      onClick={activate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') activate()
      }}
      title={`${artifact.filename} —— 点击${canPreview ? '预览' : '打开'}，或拖进输入框交给 agent`}
      className={cn(
        'group/row border-border bg-background flex items-center gap-3 rounded-lg border',
        'hover:border-foreground/20 hover:bg-muted/40 cursor-pointer px-3 py-2.5 transition-colors',
        busy && 'pointer-events-none opacity-60',
      )}
    >
      <span className="bg-muted text-muted-foreground group-hover/row:text-foreground flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition-colors">
        <Icon size={18} />
      </span>

      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-foreground truncate text-[13px] leading-tight font-medium">
          {artifact.filename}
        </span>
        <span className="text-muted-foreground text-[11px] leading-tight">
          {formatKind(artifact.filename, artifact.content_type)} ·{' '}
          {formatSize(artifact.size)} · {formatArtifactTime(artifact.created_at)}
        </span>
      </span>

      {/* 常驻可见：面板本来就是「来拿文件」的地方，藏起来等 hover 是给自己找麻烦 */}
      <button
        type="button"
        aria-label="在新标签页打开"
        onClick={(e) => {
          e.stopPropagation() // 别顺带触发外层的「预览」
          open()
        }}
        className={cn(
          'text-muted-foreground/60 hover:text-foreground hover:bg-muted',
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors',
        )}
      >
        <ExternalLink size={15} />
      </button>

      <button
        type="button"
        aria-label="下载"
        onClick={download}
        className={cn(
          'text-muted-foreground/60 hover:text-foreground hover:bg-muted',
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors',
        )}
      >
        <Download size={15} />
      </button>
    </div>
  )
}

/**
 * 产出物面板（右栏）
 *
 * **跨对话聚合**：产物绑 workspace 不绑对话（沙箱容器和对话都是临时的，
 * workspace 才是那个持久实体），所以在对话 A 里也翻得到对话 B 的产出，
 * 每组标注它出自哪个对话。
 *
 * 站内预览未做（见 issues/003），点击一律新标签页打开。
 */
export function ArtifactPanel({
  workspaceId,
  refreshKey = 0,
  onClose,
}: ArtifactPanelProps) {
  const [items, setItems] = useState<WorkspaceArtifact[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  // 预览浮层持在面板这一层而不是每行一个：同时只可能看一个文件
  const [previewing, setPreviewing] = useState<WorkspaceArtifact | null>(null)
  // 上一页拉满 = 后面大概率还有。少于一页就到底了，不必多发一次空请求
  const [hasMore, setHasMore] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await listWorkspaceArtifacts(workspaceId)
      setItems(rows)
      setHasMore(rows.length === ARTIFACT_PAGE_SIZE)
    } catch {
      // 拦截器已 toast；面板保持上一次的内容，不清空
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const rows = await listWorkspaceArtifacts(workspaceId, {
        offset: items.length,
      })
      setItems((prev) => [...prev, ...rows])
      setHasMore(rows.length === ARTIFACT_PAGE_SIZE)
    } catch {
      // 同上
    } finally {
      setLoadingMore(false)
    }
  }

  const groups = groupByConversation(items)

  // 边框比通用容器浅一档：面板是配角，别用实边框把它框得比对话区还抢眼
  return (
    <div className="bg-background border-border/50 flex h-full min-h-0 flex-col overflow-hidden rounded-lg border shadow-sm">
      {/* 头部 */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-medium">产出物</h3>
          {items.length > 0 && (
            <span className="text-muted-foreground text-xs tabular-nums">
              {items.length}
            </span>
          )}
        </div>
        <div className="-mr-1 flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon"
            aria-label="刷新"
            className="text-muted-foreground hover:text-foreground size-6"
            disabled={loading}
            onClick={() => void load()}
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="关闭"
            className="text-muted-foreground hover:text-foreground size-6"
            onClick={onClose}
          >
            <X className="size-3.5" />
          </Button>
        </div>
      </div>

      {/* 内容 */}
      {items.length === 0 ? (
        <div className="text-muted-foreground flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <FileText className="size-6 opacity-40" />
          <p className="text-xs">
            {loading ? '加载中…' : 'agent 交付的文件会沉淀在这里'}
          </p>
        </div>
      ) : (
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-3 py-3">
          {groups.map((g) => (
            <section key={g.id}>
              {/* 分组头压到最轻：它是坐标不是内容，别跟卡片抢注意力 */}
              <h4 className="text-muted-foreground/70 truncate px-1 pb-2 text-[10px] font-medium tracking-wider">
                {g.name}
              </h4>
              <div className="space-y-2">
                {g.items.map((a) => (
                  <ArtifactRow key={a.id} artifact={a} onPreview={setPreviewing} />
                ))}
              </div>
            </section>
          ))}

          {hasMore && (
            <div className="px-1 pt-1">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 w-full text-xs"
                disabled={loadingMore}
                onClick={() => void loadMore()}
              >
                {loadingMore ? '加载中…' : '加载更多'}
              </Button>
            </div>
          )}
        </div>
      )}

      <ArtifactPreviewDialog
        artifact={previewing}
        onClose={() => setPreviewing(null)}
      />
    </div>
  )
}
