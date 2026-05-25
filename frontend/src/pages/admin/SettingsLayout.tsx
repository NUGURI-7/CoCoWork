import { Link, Outlet, useRouterState } from '@tanstack/react-router'

import { settingsNav } from '@/components/layout/settings-nav.config'
import { cn } from '@/lib/utils'

/** admin 系统设置 — 左侧二级导航 + 右侧内容 */
export default function SettingsLayout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">系统设置</h1>

      <div className="flex gap-8">
        <nav className="w-40 shrink-0 space-y-1">
          {settingsNav.map((item) => {
            const active =
              pathname === item.to || pathname.startsWith(`${item.to}/`)
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                  active
                    ? 'bg-brand-subtle text-brand font-medium'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                )}
              >
                <item.icon className="size-4" />
                {item.title}
              </Link>
            )
          })}
        </nav>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
