import { useAuthStore } from '@/stores/auth'

export default function Home() {
  const user = useAuthStore((s) => s.user)

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="font-serif text-3xl">主页</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          欢迎回来{user ? `，${user.nick_name}` : ''}
        </p>
      </header>
      {/* dashboard 卡片 → 批次4 */}
    </div>
  )
}
