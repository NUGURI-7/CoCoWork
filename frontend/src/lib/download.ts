/**
 * 程序触发浏览器下载。
 *
 * 用临时 `<a download>` 而不是 `window.open` —— attachment 响应不会导航，
 * window.open 会闪出一个空白标签页。
 *
 * **`download` 属性只对同源 URL 生效**：跨源直链（如 R2 预签名 GET）由响应头
 * 里的 `Content-Disposition` 决定存成什么名字，这里给的 filename 会被忽略，
 * 所以后端签链时必须把 filename 一起签进去。
 */
export function triggerDownload(url: string, filename: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
