import { memo, useEffect, useState } from 'react'
import { helix } from 'ldrs'
import { v4 as uuidv4 } from 'uuid'

helix.register()

type MermaidApi = typeof import('mermaid').default

let mermaidPromise: Promise<MermaidApi> | null = null

/**
 * 懒加载 + 单例初始化 mermaid。
 *
 * mermaid 压缩后还有 600KB+，常驻 bundle 不值。dynamic import 首次用到才下载，
 * 模块级 Promise 缓存避免并发重复 import。
 */
function loadMermaid(): Promise<MermaidApi> {
  if (mermaidPromise) return mermaidPromise
  mermaidPromise = import('mermaid').then((mod) => {
    const mermaid = mod.default
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'strict',
      fontFamily: 'inherit',
      // 解析失败时只抛异常、不往 DOM 注入自带的「Syntax error」炸弹图 ——
      // 改由本组件 catch 后走优雅降级框（非法图表语法不该把炸弹画到用户页面上）
      suppressErrorRendering: true,
      themeVariables: {
        edgeLabelBackground: '#ffffff',
      },
    })
    return mermaid
  })
  return mermaidPromise
}

/**
 * source → svg 模块级缓存。
 *
 * - 解决多组件实例对同一 source 重复 render mermaid 的浪费
 * - 解决 React 重挂载（StrictMode dev / 父组件 key 变化等）丢失渲染结果的问题
 * - useState 初始值同步查缓存，命中直接拿到 svg
 *
 * 内存预算：单条会话的 mermaid 块数量有限，不加 LRU。
 */
const svgCache = new Map<string, string>()

/**
 * 模块级渲染队列 —— mermaid v11 render() 内部对 document.body 有共享 DOM 操作，
 * 并发 render 容易互踩（典型表现：其中一个 hang 住、SVG 不出）。
 * 用 Promise 链把所有 render 排队跑，一次只一个；失败不堵后续。
 */
let renderQueue: Promise<unknown> = Promise.resolve()

function renderSerialized(source: string): Promise<string> {
  const next = renderQueue.then(async () => {
    const mermaid = await loadMermaid()
    const id = `mermaid-${uuidv4()}`
    const { svg } = await mermaid.render(id, source)
    return svg
  })
  renderQueue = next.catch(() => undefined)
  return next
}

interface MermaidBlockProps {
  source: string
  /** 流式期不渲染 —— 避免半截源码反复 parse error + 闪烁。 */
  isStreaming?: boolean
}

/**
 * Mermaid 图表块 —— MarkdownRender 把 ```mermaid 代码块分流到这里。
 *
 * 渲染策略：
 * - 流式期间：占位 + l-tail-chase loader，不调 mermaid。
 * - 流结束：先查模块缓存命中即跳过；否则进串行队列调 mermaid.render 拿 SVG。
 * - 失败：destructive 文案 + 原始错误信息，不炸整条消息。
 *
 * 防多余重渲染：
 * - 组件外层 `memo` —— props 不变就跳过 re-render，源头掐掉滚动 / 新轮次的级联。
 * - `useState` 初始值同步查缓存 —— 即便组件被 remount 也能瞬间恢复，不闪 loader。
 */
function MermaidBlockBase({ source, isStreaming }: MermaidBlockProps) {
  const trimmed = source.trim()
  const [svg, setSvg] = useState<string | null>(() => svgCache.get(trimmed) ?? null)
  const [error, setError] = useState<string | null>(null)
  const [rendering, setRendering] = useState(false)

  useEffect(() => {
    if (isStreaming) return

    // 缓存命中：直接同步拿 svg，不进队列、不闪 loader
    const cached = svgCache.get(trimmed)
    if (cached) {
      setSvg(cached)
      setError(null)
      setRendering(false)
      return
    }

    let cancelled = false
    setRendering(true)
    setError(null)

    renderSerialized(trimmed)
      .then((rendered) => {
        svgCache.set(trimmed, rendered)
        if (cancelled) return
        setSvg(rendered)
      })
      .catch((err: unknown) => {
        // 即便 cancelled 也打 log，方便排查
        console.error('[MermaidBlock] render failed:', err)
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setError(message)
        setSvg(null)
      })
      .finally(() => {
        if (cancelled) return
        setRendering(false)
      })

    return () => {
      cancelled = true
    }
  }, [trimmed, isStreaming])

  // 流式期 / 首次加载中且无缓存 → loading 占位
  if (isStreaming || (rendering && !svg && !error)) {
    return (
      <div className="bg-card text-brand my-4 flex min-h-[120px] items-center justify-center gap-2 rounded-lg border text-sm">
        <l-helix size="20" speed="4" color="currentColor" />
        <span>正在渲染图表…</span>
      </div>
    )
  }

  // 失败兜底
  if (error) {
    return (
      <div className="bg-card my-4 flex flex-col gap-1 rounded-lg border p-4 text-sm">
        <div className="text-destructive font-medium">图表渲染失败</div>
        <div className="text-muted-foreground font-mono text-xs break-all whitespace-pre-wrap">
          {error}
        </div>
      </div>
    )
  }

  // 渲染好
  return (
    <div
      className="bg-card my-4 flex items-center justify-center overflow-x-auto rounded-lg border p-4"
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  )
}

export const MermaidBlock = memo(MermaidBlockBase)
