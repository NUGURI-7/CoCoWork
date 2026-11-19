/** 回答里的引用记号 [[cite:<段短标识>]]，与后端 knowledge_retrieval.cite_marker 的格式一致 */
const CITE_MARKER = /\[\[cite:([0-9a-f]{8})\]\]/g

/** 末尾吐了一半的记号（`[[`、`[[ci`、`[[cite:2e3f` …），流式期间先藏起来 */
const PARTIAL_CITE_TAIL = /\[\[(?:c(?:i(?:t(?:e(?::[0-9a-f]*)?)?)?)?)?$/

/** 角标在 markdown 里的载体：一个指向 `#cite-<ref>` 的链接，渲染器认到它画成角标 */
const CITE_HREF_PREFIX = '#cite-'

/**
 * 给一条回答里的引用编号：按记号首次出现的顺序从 1 起，同一段复用同一个号。
 *
 * texts 是这条回答的各个文字块，按显示顺序传入 —— 编号跨块连续，不按块各自重来。
 * 只给 known 里查得到的 ref 编号：查不到的记号不占号，渲染时直接去掉。
 */
export function numberCitations(
  texts: string[],
  known: Record<string, unknown>,
): Record<string, number> {
  const numbers: Record<string, number> = {}
  let next = 1
  for (const text of texts) {
    for (const match of text.matchAll(CITE_MARKER)) {
      const ref = match[1]
      if (ref in known && !(ref in numbers)) numbers[ref] = next++
    }
  }
  return numbers
}

/**
 * 把回答里的 `[[cite:<ref>]]` 换成角标链接 `[N](#cite-<ref>)`。
 *
 * - 编号表里有：换成角标链接
 * - 编号表里没有（模型抄错、编造）：去掉记号，句子照常显示
 * - 流式期间末尾的半截记号先切掉，写完整后下一次渲染自然换成角标
 */
export function injectCitations(
  content: string,
  numbers: Record<string, number>,
  isStreaming: boolean,
): string {
  const text = isStreaming ? content.replace(PARTIAL_CITE_TAIL, '') : content
  return text.replace(CITE_MARKER, (_, ref: string) => {
    const n = numbers[ref]
    return n === undefined ? '' : `[${n}](${CITE_HREF_PREFIX}${ref})`
  })
}

/** 角标链接的 href → ref；不是角标链接返回 null */
export function citeRefFromHref(href: string | undefined): string | null {
  return href?.startsWith(CITE_HREF_PREFIX) ? href.slice(CITE_HREF_PREFIX.length) : null
}
