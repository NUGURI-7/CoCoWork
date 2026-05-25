import { FileText, MoreHorizontal, Inbox } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { docStatusMeta, type KnowledgeDoc } from './mock'

export function DocumentList({ docs }: { docs: KnowledgeDoc[] }) {
  if (docs.length === 0) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-sm">
        <Inbox className="size-8 opacity-40" />
        <p>还没有文档</p>
        <p className="text-xs">点击右上角「上传文档」开始</p>
      </div>
    )
  }

  return (
    <div className="divide-y rounded-lg border">
      {docs.map((d) => {
        const s = docStatusMeta[d.status]
        return (
          <div
            key={d.id}
            className="hover:bg-muted/40 flex items-center gap-3 px-4 py-3 transition-colors"
          >
            <FileText className="text-muted-foreground size-4 shrink-0" />

            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{d.name}</div>
              <div className="text-muted-foreground mt-0.5 text-xs">
                {d.size} · {d.chunk_count} chunks
              </div>
            </div>

            <span className="text-muted-foreground hidden items-center gap-1.5 text-xs sm:flex">
              <span className={cn('size-1.5 rounded-full', s.dot, s.pulse && 'animate-pulse')} />
              {s.label}
            </span>

            <span className="text-muted-foreground hidden w-14 text-right text-xs md:block">
              {d.uploaded_at}
            </span>

            <Button variant="ghost" size="icon" className="size-7 shrink-0">
              <MoreHorizontal className="size-4" />
            </Button>
          </div>
        )
      })}
    </div>
  )
}
