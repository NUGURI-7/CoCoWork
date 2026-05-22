/** 临时占位页 —— 各模块页面实装后替换 */
export default function PagePlaceholder({ title }: { title: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 py-24 text-center">
      <h1 className="font-serif text-3xl">{title}</h1>
      <p className="text-muted-foreground text-sm">建设中 —— 这个模块稍后实装</p>
    </div>
  )
}
