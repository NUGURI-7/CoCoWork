import type { Figure } from '@/types'

/** 正文里的插图记号，与后端 parser/base.py 的 figure_marker 格式一致 */
const FIGURE_MARKER = /\[\[figure:(\d+)\]\]/g

/**
 * 把正文里的 `[[figure:N]]` 换成 markdown 图片 `![图 N](url)`，交给 markdown 渲染器显示。
 *
 * 解析时图自成一块，记号在正文里恒独占一个自然段，不会落进代码块或句子中间，
 * 故渲染前做一次字符串替换即可（同 MarkdownRender 里公式分隔符的预处理）。
 * 找不到对应编号的图时直接去掉记号，不把原始记号露给用户。
 */
export function injectFigures(content: string, figures: Figure[] | undefined): string {
  const urls = new Map((figures ?? []).map((f) => [f.index, f.url]))
  return content.replace(FIGURE_MARKER, (_, n: string) => {
    const url = urls.get(Number(n))
    // 尖括号包住链接：预签名 URL 带查询参数，免得特殊字符打断 markdown 链接语法
    return url ? `![图 ${n}](<${url}>)` : ''
  })
}

/** 回答里的插图记号 [[figure:<段短标识>-N]]，与后端 figure_urls.figure_ref 的格式一致 */
const ANSWER_FIGURE_MARKER = /\[\[figure:([0-9a-f]{8}-\d+)\]\]/g

/** 末尾吐了一半的记号（`[[`、`[[fig`、`[[figure:a1b2` …），流式期间先藏起来 */
const PARTIAL_MARKER_TAIL = /\[\[(?:f(?:i(?:g(?:u(?:r(?:e(?::[0-9a-f-]*)?)?)?)?)?)?)?$/

/** 链接还没签回来时的占位图地址，MarkdownImage 认到它画占位框 */
export const FIGURE_PENDING_SRC = '#figure-pending'

/**
 * 把模型回答里的 `[[figure:<段短标识>-N]]` 换成 markdown 图片。
 *
 * - 表里有：换成 `![图](url)`
 * - 表里没有、签名请求还在路上：换成占位图，链接回来后自动变成真图
 * - 表里没有、也没有在途请求：模型抄错或段已被重新解析，直接去掉
 */
export function injectAnswerFigures(
  content: string,
  urls: Record<string, string>,
  signing: boolean,
  isStreaming: boolean,
): string {
  const text = isStreaming ? content.replace(PARTIAL_MARKER_TAIL, '') : content
  return text.replace(ANSWER_FIGURE_MARKER, (_, ref: string) => {
    const url = urls[ref]
    if (url) return `![图](<${url}>)`
    return signing ? `![图片加载中](${FIGURE_PENDING_SRC})` : ''
  })
}
