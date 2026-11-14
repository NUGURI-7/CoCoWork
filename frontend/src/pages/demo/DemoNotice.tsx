import { LANDING_URL } from '@/lib/demo'

interface DemoNoticeProps {
  title: string
  description: string
}

/** 体验入口的整页说明：额度用完、场景下线、凭证过期都用它，统一引导回官网 */
export function DemoNotice({ title, description }: DemoNoticeProps) {
  return (
    <div className="bg-background grid min-h-dvh place-items-center px-4">
      <div className="max-w-sm text-center">
        <h1 className="text-foreground text-xl font-semibold">{title}</h1>
        <p className="text-muted-foreground mt-3 text-sm leading-relaxed">{description}</p>
        <a
          href={LANDING_URL}
          className="bg-primary text-primary-foreground hover:bg-primary/90 mt-8 inline-block rounded-md px-5 py-2 text-sm transition"
        >
          返回产品介绍
        </a>
      </div>
    </div>
  )
}
