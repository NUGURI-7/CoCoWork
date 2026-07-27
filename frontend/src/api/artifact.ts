/**
 * 沙箱产物 API — 对接 backend/app/api/routes/sandbox/artifact.py
 *
 * 路径前缀 `/artifacts`，加上 axios baseURL `/api/v1`。
 *
 * **URL 点击时才换**：产物卡片上只有 id / 文件名 / 大小，用户点了才来换一个
 * 短期预签名。好处是每次点击都过一遍后端归属校验，且链接不会长期有效 ——
 * 消息放三天再点也一样能开，因为拿到的永远是新鲜的。
 */

import { get } from '@/request'

/** 浏览器拿到文件后怎么处理：直接打开看 / 存成文件。 */
export type ArtifactDisposition = 'inline' | 'attachment'

/**
 * 换一个可直接打开的 URL。
 *
 * 后端两种存储后端返的形态不同，本函数统一成「拿到就能用」：
 * - R2 → 绝对 URL（对象存储直链），原样返回
 * - Local → 相对路径 `/artifacts/{id}/raw`，这里补上 API 前缀
 */
export async function getArtifactDownloadUrl(
  artifactId: string,
  disposition: ArtifactDisposition = 'inline',
): Promise<string> {
  // 注意：本项目 get() 的第二个参数**就是 params 本身**，不是 axios config，
  // 别写成 { params: { ... } } —— 那样会变成 ?params=… 且类型检查发现不了
  const { url } = await get<{ url: string }>(
    `/artifacts/${artifactId}/download-url`,
    { disposition },
  )
  return url.startsWith('http') ? url : `/api/v1${url}`
}
