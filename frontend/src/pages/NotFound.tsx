import { useNavigate } from '@tanstack/react-router'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="grid min-h-dvh place-items-center p-8">
      <div className="text-center">
        <p className="text-muted-foreground text-sm tracking-widest uppercase">404</p>
        <h1 className="font-serif mt-2 text-5xl">页面不存在</h1>
        <p className="text-muted-foreground mt-3 text-sm">该路径不存在或已被移除。</p>
        <button
          className="bg-primary text-primary-foreground hover:bg-primary/90 mt-8 rounded-md px-5 py-2 text-sm transition"
          onClick={() => navigate({ to: '/' })}
        >
          返回主页
        </button>
      </div>
    </div>
  )
}
