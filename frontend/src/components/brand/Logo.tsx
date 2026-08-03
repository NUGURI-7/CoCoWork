/**
 * 品牌标识。
 *
 * 图形语义：中心节点 = supervisor，三个卫星节点 = 被派活的成员，连线 = 调度关系。
 *
 * 取色：节点用 currentColor、连线用同色低透明度，
 * 所以只要在外层给文字色（默认 text-brand）就能整体控色，
 * 深浅色模式由 --brand token 自己切，组件里不写死任何十六进制。
 *
 * 注：项目规范要求静态图标一律走 lucide-react，这里是品牌资产例外
 * —— logo 不可能出自通用图标库。除 logo 外仍不得手写 SVG。
 */

import { cn } from '@/lib/utils'

interface LogoMarkProps {
  className?: string
}

/** 只有图形的标记，用于 sidebar 收起态、favicon 同源形状、小尺寸场景 */
export function LogoMark({ className }: LogoMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={cn('text-brand size-6 shrink-0', className)}
      aria-hidden="true"
    >
      <path
        d="M16 14V6M16 18l-7 5M16 18l7 5"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        opacity={0.45}
      />
      <circle cx="16" cy="16" r="4.6" fill="currentColor" />
      <circle cx="16" cy="4.6" r="3" fill="currentColor" />
      <circle cx="7.4" cy="24.6" r="3" fill="currentColor" />
      <circle cx="24.6" cy="24.6" r="3" fill="currentColor" />
    </svg>
  )
}

interface LogoLockupProps {
  className?: string
  /** 覆盖图形部分的尺寸 / 颜色，字标不受影响 */
  markClassName?: string
}

/** 图形 + 字标的横向组合，用于登录页、README 头图一类需要完整署名的位置 */
export function LogoLockup({ className, markClassName }: LogoLockupProps) {
  return (
    <span className={cn('flex items-center gap-2.5', className)}>
      <LogoMark className={cn('size-7', markClassName)} />
      <span className="font-display text-xl leading-none font-semibold tracking-tight">
        CoCoWork
      </span>
    </span>
  )
}
