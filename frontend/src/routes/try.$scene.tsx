/**
 * /try/:scene —— 官网「立即体验」的落点，不经登录守卫。
 *
 * 没凭证就建一个体验临时账号，再问后端这个场景该去哪，跳过去；?q= 原样带上，
 * 由新对话页预填进输入框。
 */
import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import TryScenePage from '@/pages/demo/TryScenePage'

const searchSchema = z.object({
  q: z.string().optional(),
})

export const Route = createFileRoute('/try/$scene')({
  validateSearch: searchSchema,
  component: TryScenePage,
})
