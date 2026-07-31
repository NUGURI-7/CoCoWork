/**
 * 拖产物的载荷契约 —— 产出物面板（拖的一头）与输入框（接的一头）共用一份。
 *
 * **用原生 HTML5 Drag & Drop，不引库**：这里是一次性投递（面板 → 输入框，松手就完事），
 * 没有排序、没有中间态。dnd-kit / react-dnd 买的是排序列表 + 动画 + 键盘可达性 + 触屏，
 * 我们一样都用不上。代价照实记：**原生拖放在触屏上不工作**，将来要上移动端得换指针事件。
 *
 * **自定义 MIME 而不是 text/plain**：拖到浏览器地址栏、别的输入框时不会被误当文本插入；
 * 我们自己也能一眼分辨「这是产物卡片」而不是从桌面拖来的文件。
 */

import type { Artifact } from '@/types'

/** 私有 MIME —— `x-` 前缀是「非注册类型」的惯例写法 */
export const ARTIFACT_DRAG_MIME = 'application/x-cocowork-artifact'

/** 拖的一头：把卡片信息挂上去。 */
export function setArtifactDragData(
  e: React.DragEvent,
  artifact: Artifact,
): void {
  e.dataTransfer.setData(ARTIFACT_DRAG_MIME, JSON.stringify(artifact))
  // copy 而不是 move —— 拖走之后面板里那张卡片还在（引用，不是搬运）
  e.dataTransfer.effectAllowed = 'copy'
}

/**
 * 接的一头（dragover 期间）：只能问「有没有这个类型」。
 *
 * 浏览器在拖动过程中**刻意不让读内容**（不然任意网页都能偷看你正在拖什么），
 * `getData` 这时一律返回空串，只有 `types` 可读。所以判断能不能接必须靠它。
 */
export function hasArtifactDrag(dt: DataTransfer): boolean {
  return dt.types.includes(ARTIFACT_DRAG_MIME)
}

/** 接的一头（drop 之后）：真正把内容读出来。烂数据一律当没拖。 */
export function readArtifactDragData(dt: DataTransfer): Artifact | null {
  const raw = dt.getData(ARTIFACT_DRAG_MIME)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Artifact
    return typeof parsed?.id === 'string' ? parsed : null
  } catch {
    return null
  }
}
