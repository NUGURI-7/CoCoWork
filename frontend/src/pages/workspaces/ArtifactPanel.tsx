import { FileText, X } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface ArtifactPanelProps {
  onClose: () => void
}

/**
 * 产出物面板（右栏，spec §5.5）
 *
 * v0 占位：agent 任务产出（文档/数据/图表）的时间线沉淀位。
 * 后续切片接长任务 + 产出物对象。
 */
export function ArtifactPanel({ onClose }: ArtifactPanelProps) {
  return (
    <div className="bg-background flex h-full min-h-0 flex-col overflow-hidden rounded-lg border shadow-sm">
      {/* 头部 */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-medium">产出物</h3>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground -mr-1 size-6"
          onClick={onClose}
        >
          <X className="size-3.5" />
        </Button>
      </div>

      {/* 内容：空态 */}
      <div className="text-muted-foreground flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-6 text-center text-xs">
        <FileText className="size-7" />
        <p>agent 产出的文档、数据、图表会沉淀在此</p>
        <p className="text-[11px]">后续切片接长任务 + 时间线</p>
      </div>
    </div>
  )
}
