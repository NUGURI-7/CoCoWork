import { useState } from 'react'

import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { FIGURE_PENDING_SRC } from '@/lib/figures'

import { useOptionalChatStore } from './ChatProvider'

interface MarkdownImageProps {
  src?: string
  alt?: string
}

/**
 * markdown 里的图片：宽度不超过容器、滚到附近才加载，点击弹窗看大图。
 * 知识库段预览、命中测试与对话消息共用（都经 MarkdownRender）。
 */
export function MarkdownImage({ src, alt }: MarkdownImageProps) {
  const [open, setOpen] = useState(false)
  // 对话里的插图是限时直链：加载失败多半是过期了，整份重签一次。只重试一次，免得坏图反复请求
  const chatStore = useOptionalChatStore()
  const [retried, setRetried] = useState(false)
  if (!src) return null
  if (src === FIGURE_PENDING_SRC) {
    return <Skeleton className="my-3 aspect-video w-full max-w-md rounded-md" />
  }

  const handleError = () => {
    if (!chatStore || retried) return
    setRetried(true)
    chatStore.getState().refreshFigures()
  }

  return (
    <>
      <img
        src={src}
        alt={alt ?? ''}
        loading="lazy"
        onError={handleError}
        onClick={() => setOpen(true)}
        className="my-3 max-w-full cursor-zoom-in rounded-md border"
      />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-[90vw] p-2 sm:max-w-[90vw]">
          <DialogTitle className="sr-only">{alt || '图片'}</DialogTitle>
          <img
            src={src}
            alt={alt ?? ''}
            className="mx-auto max-h-[85vh] w-auto object-contain"
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
