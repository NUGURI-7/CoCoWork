/** 临时占位页 —— 各模块页面实装后替换 */
export default function PagePlaceholder({
  title,
  description = '建设中 —— 这个模块稍后实装',
}: {
  title: string
  description?: string
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 py-24 text-center">
      <h1 className="font-display text-3xl font-semibold tracking-tight">{title}</h1>
      <p className="text-muted-foreground text-sm">{description}</p>
    </div>
  )
}
