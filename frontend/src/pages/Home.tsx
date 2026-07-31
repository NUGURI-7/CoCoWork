import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import type { LinkProps } from '@tanstack/react-router'
import { ring } from 'ldrs'
import {
  ArrowRight,
  BookOpen,
  Bot,
  Cpu,
  Inbox,
  Layers,
  Plus,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { listAgents } from '@/api/agent'
import { listKnowledgeBases } from '@/api/knowledge'
import { listAllModels } from '@/api/model'
import { listTools } from '@/api/tool'
import { listWorkspaces } from '@/api/workspace'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth'
import type { Workspace } from '@/types'

ring.register()

/** 概览卡 key 对应 counts 里的计数 */
type StatKey = 'agents' | 'knowledge' | 'models' | 'tools'

interface StatItem {
  key: StatKey
  title: string
  to: LinkProps['to']
  icon: LucideIcon
  unit: string
}

interface QuickAction {
  label: string
  to: LinkProps['to']
}

const stats: StatItem[] = [
  { key: 'agents', title: 'Agents', to: '/agents', icon: Bot, unit: '个智能体' },
  { key: 'knowledge', title: '知识库', to: '/knowledge', icon: BookOpen, unit: '个知识库' },
  { key: 'models', title: '模型', to: '/models', icon: Cpu, unit: '个已接入' },
  { key: 'tools', title: '工具', to: '/tools', icon: Wrench, unit: '个工具' },
]

const quickActions: QuickAction[] = [
  { label: '创建 Agent', to: '/agents' },
  { label: '新建知识库', to: '/knowledge' },
  { label: '接入模型', to: '/models' },
]

/** 相对时间：分钟 / 小时 / 天前 */
function timeAgo(s: string): string {
  const diff = Date.now() - new Date(s).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 60) return `${Math.max(m, 1)} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

type Counts = Record<StatKey, number | null>

const INITIAL_COUNTS: Counts = {
  agents: null,
  knowledge: null,
  models: null,
  tools: null,
}

export default function Home() {
  const user = useAuthStore((s) => s.user)
  // null = 该项加载中 / 失败 → 卡片显 —
  const [counts, setCounts] = useState<Counts>(INITIAL_COUNTS)
  // null = 加载中；[] = 无；否则最近若干条
  const [recent, setRecent] = useState<Workspace[] | null>(null)

  useEffect(() => {
    let cancelled = false

    // allSettled：单个模块接口挂掉不连累整个看板（其余计数照常显示）
    Promise.allSettled([
      listAgents(),
      listKnowledgeBases(),
      listAllModels(),
      listTools(),
      listWorkspaces(),
    ]).then(([agents, knowledge, models, tools, workspaces]) => {
      if (cancelled) return
      const len = (r: PromiseSettledResult<unknown[]>) =>
        r.status === 'fulfilled' ? r.value.length : null
      setCounts({
        agents: len(agents),
        knowledge: len(knowledge),
        models: len(models),
        tools: len(tools),
      })
      const ws = workspaces.status === 'fulfilled' ? workspaces.value : []
      setRecent(
        [...ws]
          .sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at))
          .slice(0, 5),
      )
    })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex flex-col gap-8">
      {/* 顶部问候 + 主操作 */}
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">主页</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {user?.nick_name
              ? `欢迎回来，${user.nick_name}`
              : '欢迎回来，开始今天的工作'}
          </p>
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
        {stats.map((item) => {
          const count = counts[item.key]
          return (
            <Link key={item.key} to={item.to}>
              <Card className="card-interactive gap-4">
                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-sm">{item.title}</span>
                    <item.icon className="text-brand size-5" />
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-mono text-3xl leading-none font-medium tabular-nums">
                      {count ?? '—'}
                    </span>
                    <span className="text-muted-foreground text-xs">{item.unit}</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </section>

      {/* 下半区：最近的工作空间 + 快捷入口 */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="flex flex-col gap-4">
            <h2 className="text-sm font-medium">最近的工作空间</h2>
            <RecentWorkspaces recent={recent} />
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

/** 最近工作空间列表：加载中 / 空态 / 列表三态 */
function RecentWorkspaces({ recent }: { recent: Workspace[] | null }) {
  if (recent === null) {
    return (
      <div className="flex items-center justify-center py-12">
        <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }

  if (recent.length === 0) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 py-12">
        <Inbox className="size-8 opacity-40" />
        <p className="text-sm">还没有工作空间</p>
        <Link to="/workspaces" className="text-brand text-xs hover:underline">
          去创建一个
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-0.5">
      {recent.map((w) => (
        <Link
          key={w.id}
          to="/workspaces/$workspaceId"
          params={{ workspaceId: w.id }}
          className="hover:bg-muted group flex items-center gap-3 rounded-md px-2 py-2 transition"
        >
          {w.avatar_url ? (
            <img
              src={w.avatar_url}
              alt={w.name}
              className="size-8 shrink-0 rounded-md object-cover"
            />
          ) : (
            <div className="bg-brand-subtle text-brand flex size-8 shrink-0 items-center justify-center rounded-md">
              <Layers className="size-4" />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{w.name}</div>
            <div className="text-muted-foreground text-[11px]">
              {timeAgo(w.updated_at)}
            </div>
          </div>
          <ArrowRight className="text-muted-foreground size-4 shrink-0 opacity-0 transition group-hover:opacity-100" />
        </Link>
      ))}
    </div>
  )
}
