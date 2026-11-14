import { GUEST_QUOTA_EXHAUSTED_HINT } from './guest-quota'

/** 输入框上方的一行剩余次数提示；remaining 为 null 时不渲染 */
export function GuestQuotaHint({ remaining }: { remaining: number | null }) {
  if (remaining === null) return null
  return (
    <p className="text-muted-foreground mx-auto w-full max-w-3xl px-4 pb-1.5 text-center text-xs">
      {remaining > 0 ? `今日还可体验 ${remaining} 次` : GUEST_QUOTA_EXHAUSTED_HINT}
    </p>
  )
}
