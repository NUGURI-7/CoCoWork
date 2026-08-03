/**
 * Agent / 工作空间成员头像。
 *
 * 没有自定义头像时按 seed 生成一张确定的脸（DiceBear bottts 风格，
 * 作者声明「个人与商业用途均免费」，无需署名）。
 *
 * 生成是**确定性**的，不是随机：同一个 seed 永远得到同一张脸，
 * 所以头像本身不需要落库 —— 存住 seed（= agent.id）就等于存住了头像。
 *
 * seed 一律用 **id 而非名字**：改名不换脸，同一个 agent 在任何工作空间
 * 都是同一张脸；管家是每个空间自带的同一种角色，固定用 'supervisor'。
 *
 * 生成结果按 seed 缓存在模块级 Map —— 列表滚动、重渲染不会反复算 SVG。
 */

import { createAvatar } from '@dicebear/core'
import { bottts } from '@dicebear/collection'
import { useMemo } from 'react'

import { cn } from '@/lib/utils'

/** 管家没有 agent id，全站共用这个 seed */
export const SUPERVISOR_SEED = 'supervisor'

const uriCache = new Map<string, string>()

function generatedAvatar(seed: string): string {
  const cached = uriCache.get(seed)
  if (cached) return cached

  const uri = createAvatar(bottts, { seed, size: 96 }).toDataUri()
  uriCache.set(seed, uri)
  return uri
}

/**
 * 取头像地址的纯函数版本。
 * 只在需要把地址塞进 state / 传给不接受组件的第三方结构时用（如 mention 候选项），
 * 能用 <AgentAvatar> 的地方就别用它。
 */
export function agentAvatarUrl(seed: string, src?: string | null): string {
  return src ?? generatedAvatar(seed)
}

interface AgentAvatarProps {
  /** 稳定标识：agent 传 agent.id，管家传 SUPERVISOR_SEED */
  seed: string
  /** 用户自定义头像；给了就优先用，为将来的上传功能留的口子 */
  src?: string | null
  alt?: string
  className?: string
}

export function AgentAvatar({ seed, src, alt = '', className }: AgentAvatarProps) {
  const url = useMemo(() => agentAvatarUrl(seed, src), [seed, src])

  return (
    <img
      src={url}
      alt={alt}
      className={cn('bg-muted size-8 shrink-0 rounded-full object-cover', className)}
    />
  )
}
