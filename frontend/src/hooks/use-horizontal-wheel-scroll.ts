/**
 * 鼠标垂直滚轮 → 容器横向滚动
 *
 * 用法：
 *   const ref = useHorizontalWheelScroll<HTMLDivElement>()
 *   <div ref={ref} className="overflow-x-auto">...</div>
 *
 * 说明：
 * - React 的 onWheel 默认是 passive listener，preventDefault 不生效，
 *   所以这里用 ref + 原生 addEventListener({ passive: false })
 * - trackpad 双指横向滑原生已支持，本 hook 主要服务鼠标用户
 */

import { useEffect, useRef } from 'react'

export function useHorizontalWheelScroll<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY === 0) return
      e.preventDefault()
      el.scrollLeft += e.deltaY
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  return ref
}
