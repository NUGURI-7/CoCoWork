/**
 * 输入框前置图标容器（纯装饰）
 *  - 图标作为 FormControl 的兄弟节点放在 relative 外层，
 *    保证 FormControl(Slot) 注入的 id/aria-* 仍落到 Input 上。
 *  - children 传入 <FormControl><Input className="pl-9" /></FormControl>
 */

import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface IconFieldProps {
  icon: LucideIcon
  children: ReactNode
}

export default function IconField({ icon: Icon, children }: IconFieldProps) {
  return (
    <div className="relative">
      <Icon
        className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
        aria-hidden
      />
      {children}
    </div>
  )
}
