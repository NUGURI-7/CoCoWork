import { useState } from 'react'

import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'

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
  if (!src) return null

  return (
    <>
      <img
        src={src}
        alt={alt ?? ''}
        loading="lazy"
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
