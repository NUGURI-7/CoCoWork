import { useAuthStore } from '@/stores/auth'

export default function Home() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  function handleLogout() {
    logout()
    window.location.href = '/login'
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-6 px-6">
      <header>
        <h1 className="font-serif text-5xl">CoCoWork</h1>
        <p className="text-muted-foreground mt-2 text-sm">登录成功 — 占位主页</p>
      </header>

      {user && (
        <section className="bg-card rounded-lg border p-6">
          <h2 className="mb-3 text-sm font-medium tracking-wide uppercase">Current user</h2>
          <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
            <dt className="text-muted-foreground">username</dt>
            <dd>{user.username}</dd>
            <dt className="text-muted-foreground">nick_name</dt>
            <dd>{user.nick_name}</dd>
            <dt className="text-muted-foreground">email</dt>
            <dd>{user.email}</dd>
            <dt className="text-muted-foreground">is_admin</dt>
            <dd>{String(user.is_admin)}</dd>
          </dl>
        </section>
      )}

      <button
        className="bg-primary text-primary-foreground hover:bg-primary/90 self-start rounded-md px-4 py-2 text-sm transition"
        onClick={handleLogout}
      >
        退出登录
      </button>
    </main>
  )
}
