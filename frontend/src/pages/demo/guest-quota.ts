import { useEffect, useState } from 'react'

import { getSceneQuota } from '@/api/demo'
import { useChat } from '@/components/chat/ChatProvider'
import { useAuthStore } from '@/stores/auth'

/** 次数用完时输入框的禁用提示，也是提示行的文案 */
export const GUEST_QUOTA_EXHAUSTED_HINT = '今天的体验次数已用完，欢迎明天再来'

/**
 * 体验访客在这个场景今天还剩几次；正式用户返回 null（不显示、不限制）。
 * 进页面取一次，每次回复结束（isLoading 落回 false）再取一次。须在 ChatProvider 内使用。
 */
export function useGuestQuota(targetId: string): number | null {
  const guest = useAuthStore((s) => s.user?.is_guest === true)
  const isLoading = useChat((s) => s.isLoading)
  const [remaining, setRemaining] = useState<number | null>(null)

  useEffect(() => {
    if (!guest || isLoading) return
    let cancelled = false
    getSceneQuota(targetId)
      .then((q) => {
        if (!cancelled) setRemaining(q.remaining)
      })
      .catch(() => {
        /* 取不到就不显示，不影响发消息；真超限时后端会拦 */
      })
    return () => {
      cancelled = true
    }
  }, [guest, targetId, isLoading])

  return guest ? remaining : null
}
