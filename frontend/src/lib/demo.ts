/** 官网免登录体验的前端约定 */

/** 产品介绍页地址：访客体验过期、场景不可用时引导回这里重新进入 */
export const LANDING_URL = 'https://cocowork.nuguri.org'

/** 当前凭证是不是体验访客的。凭证本身不带这个信息，签发时单独记一笔 */
export const GUEST_FLAG_KEY = 'guest'

/** 凭证失效时该去哪：访客没有密码，去体验说明页；正式用户去登录页 */
export function signInPath(): string {
  return localStorage.getItem(GUEST_FLAG_KEY) ? '/try' : '/login'
}
