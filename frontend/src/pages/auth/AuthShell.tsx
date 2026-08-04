/**
 * 登录 / 注册共用双栏布局壳（Claude 风）
 *  - 顶部：logo wordmark（左）+ navAction（右，放切换链接）
 *  - 左列：children（表单内容）
 *  - 右列：WorkspacePreview 产品演示动画（lg 以上显示）
 */

import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { LogoLockup } from '@/components/brand/Logo'
import WorkspacePreview from './WorkspacePreview'

interface AuthShellProps {
  children: ReactNode
  navAction?: ReactNode
}

export default function AuthShell({ children, navAction }: AuthShellProps) {
  return (
    <div className="bg-background flex min-h-dvh flex-col duration-500 animate-in fade-in">
      {/* 顶部 nav */}
      <header className="flex h-16 items-center justify-between px-6 lg:px-10">
        <Link to="/">
          <LogoLockup />
        </Link>
        {navAction}
      </header>

      {/* 主体双栏 */}
      <div className="mx-auto grid min-h-0 w-full max-w-7xl flex-1 pb-16 lg:grid-cols-2">
        {/* 左列：表单 */}
        <div className="flex items-center justify-center px-6 py-10 lg:px-16">
          <div className="w-full max-w-sm">{children}</div>
        </div>

        {/* 右列：产品演示动画（lg+）—— 首屏无声地演一遍「多 Agent 派活」是什么样 */}
        <div className="hidden items-center justify-center p-10 lg:flex">
          <div className="fill-mode-both delay-150 duration-700 animate-in fade-in slide-in-from-bottom-4">
            <WorkspacePreview />
          </div>
        </div>
      </div>
    </div>
  )
}
