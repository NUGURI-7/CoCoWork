import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { isAxiosError } from 'axios'
import { ring } from 'ldrs'

import { getSceneEntry } from '@/api/demo'
import { ApiBusinessError } from '@/request'
import { useAuthStore } from '@/stores/auth'
import type { SceneEntry } from '@/types'

import { DemoNotice } from './DemoNotice'

ring.register()

type Failure = { title: string; description: string }

const FAILURES: Record<number, Failure> = {
  404: { title: '这个体验场景不存在', description: '链接可能已经失效，请回到产品介绍页重新选择。' },
  409: { title: '这个场景暂时下线了', description: '请稍后再来，或回到产品介绍页体验其他场景。' },
  429: { title: '今天的体验次数已用完', description: '每天的体验额度有限，欢迎明天再来。' },
}

const UNKNOWN_FAILURE: Failure = {
  title: '暂时进不去',
  description: '体验服务出了点问题，请稍后再试。',
}

function failureOf(err: unknown): Failure {
  if (err instanceof ApiBusinessError) return FAILURES[err.code] ?? UNKNOWN_FAILURE
  return UNKNOWN_FAILURE
}

function isUnauthorized(err: unknown): boolean {
  return isAxiosError(err) && err.response?.status === 401
}

/**
 * 体验入口：保证有凭证 → 解析场景 → 跳到对应的新对话页。
 *
 * 已登录（含上次留下的体验凭证）就沿用；凭证已过期或后端不认了（临时账号已被清理），
 * 丢掉它换一个新的临时账号，只重来一次。
 */
export default function TryScenePage() {
  const { scene } = useParams({ from: '/try/$scene' })
  const { q } = useSearch({ from: '/try/$scene' })
  const navigate = useNavigate()
  const [failure, setFailure] = useState<Failure | null>(null)

  useEffect(() => {
    let cancelled = false

    async function ensureSession(): Promise<void> {
      const auth = useAuthStore.getState()
      if (auth.isLoggedIn() && !auth.isExpired()) return
      auth.logout()
      await auth.signInAsGuest()
    }

    async function resolve(): Promise<SceneEntry> {
      await ensureSession()
      try {
        return await getSceneEntry(scene)
      } catch (err) {
        if (!isUnauthorized(err)) throw err
        useAuthStore.getState().logout()
        await useAuthStore.getState().signInAsGuest()
        return getSceneEntry(scene)
      }
    }

    resolve()
      .then((entry) => {
        if (cancelled) return
        const search = q ? { q } : {}
        if (entry.kind === 'agent') {
          navigate({
            to: '/chat/$agentId/new',
            params: { agentId: entry.target_id },
            search,
            replace: true,
          })
        } else {
          navigate({
            to: '/workspaces/$workspaceId/new',
            params: { workspaceId: entry.target_id },
            search,
            replace: true,
          })
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setFailure(failureOf(err))
      })

    return () => {
      cancelled = true
    }
  }, [scene, q, navigate])

  if (failure) return <DemoNotice title={failure.title} description={failure.description} />

  return (
    <div className="bg-background grid min-h-dvh place-items-center">
      <div className="flex flex-col items-center gap-4">
        <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
        <p className="text-muted-foreground text-sm">正在准备体验环境…</p>
      </div>
    </div>
  )
}
