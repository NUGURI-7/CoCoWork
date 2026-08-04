/**
 * Agent API — 对接 backend/app/api/routes/agent/agent.py
 *
 * 路径前缀 `/agents`，加上 axios baseURL `/api/v1`。
 */

import { del, get, post, put } from '@/request'
import type { Agent, AgentConfig, Template } from '@/types'

/** 创建 Agent 请求体（对齐后端 `AgentCreate`）。 */
export interface AgentCreatePayload {
  name: string
  description?: string
  /** 引用的内置模板 registry key */
  template: string
  config?: AgentConfig
}

/** 更新 Agent 请求体（对齐后端 `AgentUpdate`）。template 创建后锁死、不在 body。 */
export interface AgentUpdatePayload {
  name?: string
  description?: string
  config?: AgentConfig
}

/** 列出当前用户的 Agent。 */
export function listAgents() {
  return get<Agent[]>('/agents')
}

/**
 * 内置模板池。整个进程一份常量，所以缓存住首次请求的 Promise —— 多个组件
 * （列表页 / 创建弹窗 / Agent 卡片 / 配置面板）都要按 key 查模板名，各拉一次
 * 就是白发几趟请求。它只会随后端发版变，页面生命周期内不会变。
 */
let templatesPromise: Promise<Template[]> | null = null

export function listTemplates() {
  templatesPromise ??= get<Template[]>('/agents/templates').catch((err) => {
    templatesPromise = null // 失败不留坑，下次进来重试
    throw err
  })
  return templatesPromise
}

/** 获取单个 Agent 详情。 */
export function getAgent(id: string) {
  return get<Agent>(`/agents/${id}`)
}

/** 创建 Agent。走 silent 由表单层 toast，方便显示后端具体原因（如模板不存在）。 */
export function createAgent(payload: AgentCreatePayload) {
  return post<Agent>('/agents', payload, { silent: true })
}

/** 更新 Agent（整体 PUT，template 不变）。走 silent 由表单层 toast。 */
export function updateAgent(id: string, payload: AgentUpdatePayload) {
  return put<Agent>(`/agents/${id}`, payload, { silent: true })
}

/** 删除 Agent。 */
export function deleteAgent(id: string) {
  return del<null>(`/agents/${id}`)
}
