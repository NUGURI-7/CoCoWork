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
