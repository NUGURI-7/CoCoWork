import { isValidElement } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

import { cn } from '@/lib/utils'

import { CodeBlock } from './CodeBlock'
import { MermaidBlock } from './MermaidBlock'

import 'katex/dist/katex.min.css'
import 'highlight.js/styles/github.css'

/**
 * Markdown 渲染器 —— Chat / Playground / Workspace 共用。
 *
 * 设计点：
 * - react-markdown + remark-gfm：基础 markdown + GFM（表格 / 删除线 / 任务列表）。
 * - 数学公式：remark-math 解析 `$...$` / `$$...$$`，rehype-katex 渲染（KaTeX 比
 *   MathJax 轻量快，react-markdown 文档官方示例同款）。
 * - LaTeX 定界符归一化：DeepSeek / GPT 等模型默认吐 `\[ ... \]` / `\( ... \)`，
 *   不被 remark-math 识别。`normalizeLatexDelimiters` 在 render 前转成 `$$ ... $$` /
 *   `$ ... $`，并按 fenced code / inline code 切片避开代码块误转。Open WebUI /
 *   LobeChat 等开源对话项目同款做法。
 * - 不引 morphdom：React VDOM 自身 diff 流式效率够，旧版 Vue 用 morphdom 是补 Vue
 *   字符串拼接更新的短板。
 * - 流式状态指示走消息级 loader（MessageList AssistantMessageRow 底部 icon），
 *   不在 Markdown 内嵌 inline cursor —— 跟 ChatGPT / Claude / Lovable 风格一致。
 * - 代码高亮：自渲染走 `components.pre` 替换为 `CodeBlock`，hljs 高亮 + Header
 *   (语言标签 + Copy)。覆盖 `pre` 而非 `code` —— 所有 fenced code 不论有无语言都
 *   走 CodeBlock 拿到统一外壳；inline `code` 维持 prose 默认样式。不走 rehype-
 *   highlight 避开「children 已 token 化、提取原文反复折腾」的问题。dark mode
 *   主题切换后续做（github.css 是 light only）。
 * - Mermaid：`lang === 'mermaid'` 分流到 MermaidBlock（懒加载 mermaid lib +
 *   流式期占位 + 完成后渲染 SVG）。
 *
 * 容器走 Tailwind Typography `prose` 类标准化排版（@plugin '@tailwindcss/typography'
 * 已在 app.css 启用）。
 */
/** 把 LaTeX 标准定界符转 markdown 风格，避开代码块。 */
const CODE_SEGMENT_RE = /(```[\s\S]*?```|`[^`\n]*`)/g
const BLOCK_LATEX_RE = /\\\[([\s\S]+?)\\\]/g
const INLINE_LATEX_RE = /\\\(([\s\S]+?)\\\)/g

function convertProse(text: string): string {
  return text
    .replace(BLOCK_LATEX_RE, (_, body: string) => `$$${body}$$`)
    .replace(INLINE_LATEX_RE, (_, body: string) => `$${body}$`)
}

function normalizeLatexDelimiters(content: string): string {
  const out: string[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  CODE_SEGMENT_RE.lastIndex = 0
  while ((match = CODE_SEGMENT_RE.exec(content)) !== null) {
    out.push(convertProse(content.slice(lastIndex, match.index)))
    out.push(match[0]) // 代码段原样保留
    lastIndex = CODE_SEGMENT_RE.lastIndex
  }
  out.push(convertProse(content.slice(lastIndex)))
  return out.join('')
}

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
        'prose prose-base dark:prose-invert max-w-none',
        // prose 默认正文是它自带的灰，接上主题 --foreground（near-black）才是标准对话正文色
        '[--tw-prose-body:var(--foreground)] [--tw-prose-headings:var(--foreground)] [--tw-prose-bold:var(--foreground)]',
        'prose-p:leading-relaxed prose-pre:p-0 prose-pre:m-0 prose-pre:bg-transparent prose-pre:text-foreground',
        'prose-code:before:hidden prose-code:after:hidden prose-code:font-normal prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.875em]',
        isUser && 'break-words',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          pre({ children }) {
            // react-markdown 给 pre 的 children 总是单个 <code> 元素
            // （markdown spec：fenced code 一定是 pre > code 结构）
            if (
              isValidElement<{ className?: string; children?: React.ReactNode }>(children) &&
              children.type === 'code'
            ) {
              const { className, children: codeChildren } = children.props
              const match = /language-(\w+)/.exec(className ?? '')
              const lang = match?.[1] ?? ''
              const source = String(codeChildren ?? '').replace(/\n$/, '')
              if (lang === 'mermaid') {
                return <MermaidBlock source={source} isStreaming={isStreaming} />
              }
              return <CodeBlock lang={lang} source={source} />
            }
            // 兜底（极少触发）：原样吐出
            return <pre>{children}</pre>
          },
        }}
      >
        {normalizeLatexDelimiters(content)}
      </ReactMarkdown>
    </div>
  )
}
