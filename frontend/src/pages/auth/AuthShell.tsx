/**
 * 登录 / 注册共用双栏布局壳（Claude 风）
 *  - 顶部：logo wordmark（左）+ navAction（右，放切换链接）
 *  - 左列：children（表单内容）
 *  - 右列：gopher 视觉卡（lg 以上显示）
 */

import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

interface AuthShellProps {
  children: ReactNode
  navAction?: ReactNode
}

export default function AuthShell({ children, navAction }: AuthShellProps) {
  return (
    <div className="bg-background flex min-h-dvh flex-col duration-500 animate-in fade-in">
      {/* 顶部 nav */}
      <header className="flex h-16 items-center justify-between px-6 lg:px-10">
        <Link to="/" className="flex items-center gap-2">
          <img src="/mark-rotating.svg" className="size-7" alt="CoCoWork" />
          <span className="font-display text-xl font-semibold tracking-tight">CoCoWork</span>
        </Link>
        {navAction}
      </header>

      {/* 主体双栏 */}
      <div className="mx-auto grid min-h-0 w-full max-w-7xl flex-1 pb-16 lg:grid-cols-2">
        {/* 左列：表单 */}
        <div className="flex items-center justify-center px-6 py-10 lg:px-16">
          <div className="w-full max-w-sm">{children}</div>
        </div>

        {/* 右列：两张 gopher 错落叠放（lg+，无卡片背景） */}
        <div className="hidden items-center justify-center p-10 lg:flex">
          <div className="relative aspect-square w-full max-w-lg">
            {/* 背景图：右上，偏小，向中间靠 */}
            <img
              src="/gopher-fcb-glass.png"
              className="absolute top-[4%] right-0 w-[58%] object-contain duration-700 animate-in fade-in zoom-in-95"
              alt="CoCoWork mascot"
            />
            {/* 前景图：左下，偏大，向中间靠，叠在上层 + 投影 */}
            <img
              src="/gopher-dao.png"
              className="absolute bottom-[2%] left-0 z-10 w-[66%] object-contain drop-shadow-xl fill-mode-both delay-150 duration-700 animate-in fade-in slide-in-from-bottom-4"
              alt="CoCoWork mascot"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
