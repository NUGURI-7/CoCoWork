/**
 * 内置模板池的读取 hook。
 *
 * 四个地方要用它：列表页的模板条、创建弹窗的选择格、Agent 卡片和配置面板的
 * 「这个 Agent 是什么模板」。请求本身在 api 层缓存（listTemplates），所以这里
 * 每个组件各调各的不会重复发请求。
 */

import { useEffect, useState } from 'react'

import { listTemplates } from '@/api/agent'
import type { Template } from '@/types'

export function useTemplates() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    listTemplates()
      .then((list) => {
        if (alive) setTemplates(list)
      })
      .catch(() => {
        // 静默失败：模板池拉不到时页面照常可用（已有 Agent 不受影响），
        // 只是模板条为空、卡片回落显示 key
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  return { templates, loading }
}

/** 按 key 查模板，查不到返回 null（模板下架 / 还没拉到）。 */
export function findTemplate(templates: Template[], key: string) {
  return templates.find((t) => t.key === key) ?? null
}
