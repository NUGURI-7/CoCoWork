/**
 * 通用复制工具 —— 兼容 secure / 非 secure context。
 *
 * `navigator.clipboard` 属于 Web Clipboard API，仅在 secure context
 * （HTTPS / localhost）下存在；HTTP 裸 IP+端口部署时为 undefined，直接调用会抛错。
 * 故优先走 Clipboard API，不可用时降级到 `document.execCommand('copy')`
 * （临时 textarea 选中复制），后者在非安全上下文同样可用。
 *
 * @returns 是否复制成功
 */
export async function copyText(text: string): Promise<boolean> {
  // 优先：现代 Clipboard API（需 secure context）
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 落到下方降级方案
    }
  }

  // 降级：execCommand —— 非安全上下文（HTTP 裸 IP）下唯一可用路径
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    // 移出视口、避免触发滚动/聚焦抖动
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.left = '-9999px'
    textarea.setAttribute('readonly', '')
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}
