import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { cn } from '@/lib/utils'

/**
 * Markdown 渲染器 —— Chat / Playground / Workspace 共用。
 *
 * 设计点：
 * - react-markdown + remark-gfm：基础 markdown + GFM（表格 / 删除线 / 任务列表）。
 * - 不引 morphdom：React VDOM 自身 diff 流式效率够，旧版 Vue 用 morphdom 是补 Vue
 *   字符串拼接更新的短板。
 * - 流式状态指示走消息级 loader（MessageList AssistantMessageRow 底部 icon），
 *   不在 Markdown 内嵌 inline cursor —— 跟 ChatGPT / Claude / Lovable 风格一致。
 * - 代码高亮：P0 不上（pre 等宽够看）；P1 接 rehype-highlight / shiki。
 * - Mermaid：P2 再说。
 *
 * 容器走 Tailwind Typography `prose` 类标准化排版（@plugin '@tailwindcss/typography'
 * 已在 app.css 启用）。
 */
interface MarkdownRenderProps {
  content: string
  /** 流式期标识 —— P0 未消费、保留口子（未来 Mermaid / 高昂渲染按需禁用） */
  isStreaming?: boolean
  /** true = user 消息（自动换行触发 break-words，避免长链接撑爆气泡） */
  isUser?: boolean
  className?: string
}

export function MarkdownRender({
  content,
  isStreaming,
  isUser,
  className,
}: MarkdownRenderProps) {
  return (
    <div
      className={cn(
        'prose prose-sm dark:prose-invert max-w-none',
        'prose-p:leading-relaxed prose-pre:p-0 prose-pre:m-0 prose-pre:bg-transparent',
        isUser && 'break-words',
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
