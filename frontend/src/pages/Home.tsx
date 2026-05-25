import { Link } from '@tanstack/react-router'
import { Bot, BookOpen, Cpu, Wrench, Plus, ArrowRight, Inbox } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { LinkProps } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

interface StatItem {
  title: string
  to: LinkProps['to']
  icon: LucideIcon
  unit: string
}

interface QuickAction {
  label: string
  to: LinkProps['to']
}

/** 概览卡（数字暂为占位，待各模块接口就绪后接真数） */
const stats: StatItem[] = [
  { title: 'Agents', to: '/agents', icon: Bot, unit: '个智能体' },
  { title: '知识库', to: '/knowledge', icon: BookOpen, unit: '个知识库' },
  { title: '模型', to: '/models', icon: Cpu, unit: '个已接入' },
  { title: '工具', to: '/tools', icon: Wrench, unit: '待定' },
]

/** 快捷入口 */
const quickActions: QuickAction[] = [
  { label: '创建 Agent', to: '/agents' },
  { label: '新建知识库', to: '/knowledge' },
  { label: '接入模型', to: '/models' },
]

export default function Home() {
  return (
    <div className="flex flex-col gap-8">
      {/* 顶部问候 + 主操作 */}
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">主页</h1>
          <p className="text-muted-foreground mt-1 text-sm">欢迎回来，开始今天的工作</p>
        </div>
        <Button asChild>
          <Link to="/agents">
            <Plus />
            新建 Agent
          </Link>
        </Button>
      </header>

      {/* 概览统计卡 */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((item) => (
          <Link key={item.title} to={item.to}>
            <Card className="card-interactive gap-4">
              <CardContent className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground text-sm">{item.title}</span>
                  <item.icon className="text-brand size-5" />
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="font-serif text-3xl leading-none">—</span>
                  <span className="text-muted-foreground text-xs">{item.unit}</span>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>

      {/* 下半区：最近使用 + 快捷入口 */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* 最近使用（暂无数据，空态占位） */}
        <Card className="lg:col-span-2">
          <CardContent className="flex flex-col gap-4">
            <h2 className="text-sm font-medium">最近使用</h2>
            <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 py-12">
              <Inbox className="size-8 opacity-40" />
              <p className="text-sm">暂无记录</p>
            </div>
          </CardContent>
        </Card>

        {/* 快捷入口 */}
        <Card>
          <CardContent className="flex flex-col gap-4">
            <h2 className="text-sm font-medium">快捷入口</h2>
            <div className="flex flex-col gap-2">
              {quickActions.map((action) => (
                <Button key={action.label} asChild variant="outline" className="justify-between">
                  <Link to={action.to}>
                    <span className="flex items-center gap-2">
                      <Plus className="text-muted-foreground" />
                      {action.label}
                    </span>
                    <ArrowRight className="text-muted-foreground" />
                  </Link>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
