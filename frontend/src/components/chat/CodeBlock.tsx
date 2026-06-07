import { useMemo, useState } from 'react'
import hljs from 'highlight.js'
import { Check, Copy } from 'lucide-react'

import { cn } from '@/lib/utils'

/**
 * AI 输出五花八门的语言标签 → hljs 认识的标准名。
 * 只列 hljs 原生 alias 不覆盖的情况。
 */
const LANG_ALIAS: Record<string, string> = {
  // Shell 家族
  sh: 'bash',
  shell: 'bash',
  zsh: 'bash',
  console: 'bash',
  terminal: 'bash',

  // JS 家族
  node: 'javascript',
  nodejs: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',

  // TS / JSX 变体
  tsx: 'typescript',
  jsx: 'javascript',
  'typescript-jsx': 'typescript',

  // Vue / Svelte（hljs 无原生支持，降级到 HTML）
  vue: 'xml',
  svelte: 'xml',
  html: 'xml',

  // 其他常见变体
  yml: 'yaml',
  md: 'markdown',
  'c++': 'cpp',
  'c#': 'csharp',
  'objective-c': 'objectivec',
  objc: 'objectivec',
  golang: 'go',
  rs: 'rust',
  kt: 'kotlin',
  py3: 'python',
  py2: 'python',
  ipython: 'python',

  // 无语言 / 纯文本
  text: 'plaintext',
  txt: 'plaintext',
  plain: 'plaintext',
  raw: 'plaintext',
}

/** Header 左上角显示名美化（归一化后的标准名 → 漂亮名）。 */
const DISPLAY_NAME: Record<string, string> = {
  javascript: 'JavaScript',
  typescript: 'TypeScript',
  python: 'Python',
  bash: 'Bash',
  json: 'JSON',
  yaml: 'YAML',
  xml: 'HTML',
  css: 'CSS',
  scss: 'SCSS',
  go: 'Go',
  rust: 'Rust',
  java: 'Java',
  kotlin: 'Kotlin',
  swift: 'Swift',
  cpp: 'C++',
  csharp: 'C#',
  ruby: 'Ruby',
  php: 'PHP',
  sql: 'SQL',
  markdown: 'Markdown',
  dockerfile: 'Dockerfile',
  plaintext: 'Text',
}

function normalizeLang(raw: string): string {
  const lower = raw.trim().toLowerCase()
  if (!lower) return ''
  if (LANG_ALIAS[lower]) return LANG_ALIAS[lower]
  if (hljs.getLanguage(lower)) return lower
  return ''
}

function prettyLangName(normalized: string, original: string): string {
  if (!normalized) return original ? original.toUpperCase() : 'CODE'
  return DISPLAY_NAME[normalized] ?? normalized.toUpperCase()
}

interface CodeBlockProps {
  /** fenced code 的语言标签原值（未归一化），如 `tsx` / `golang`。 */
  lang: string
  /** 代码原文。 */
  source: string
}

/**
 * 代码块 —— MarkdownRender 的 `components.code` 替换体。
 *
 * 设计点：
 * - hljs 自渲染高亮 HTML（不走 rehype-highlight）—— `dangerouslySetInnerHTML`
 *   直接注入 token spans，避免 react-markdown 把 children 序列化成 React 元素
 *   后再提取文本的来回反复。
 * - Header 横条：左语言标签 + 右 Copy 按钮（DaisyWind 同款布局）。
 * - 语言归一化 + 显示名美化两张表，应对 AI 写啥都吃。
 * - hljs 不认或解析失败 → 降级为 escaped 纯文本，不炸。
 * - Copy 状态用 React state 闪 1.5s 自复位，不靠 DOM dataset 等魔法。
 */
export function CodeBlock({ lang: rawLang, source }: CodeBlockProps) {
  const normalized = normalizeLang(rawLang)
  const display = prettyLangName(normalized, rawLang)

  const highlighted = useMemo(() => {
    if (!normalized) return null
    try {
      return hljs.highlight(source, {
        language: normalized,
        ignoreIllegals: true,
      }).value
    } catch {
      return null
    }
  }, [normalized, source])

  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(source)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // 权限拒绝 / 不支持 —— 静默失败，不打扰
    }
  }

  return (
    <div className="bg-card my-4 overflow-hidden rounded-lg border">
      <div className="bg-muted/40 text-muted-foreground flex items-center justify-between border-b px-4 py-1.5">
        <span className="font-mono text-xs">{display}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="hover:text-foreground inline-flex cursor-pointer items-center gap-1 text-xs transition-colors"
          title="复制"
        >
          {copied ? (
            <>
              <Check className="text-success size-3.5" />
              <span className="text-success">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="size-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed">
        {highlighted ? (
          <code
            className={cn('hljs', normalized && `language-${normalized}`)}
            dangerouslySetInnerHTML={{ __html: highlighted }}
          />
        ) : (
          <code className="hljs">{source}</code>
        )}
      </pre>
    </div>
  )
}
