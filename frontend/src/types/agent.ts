/**
 * Agent 模块类型 — 前端先行定义，后端实现时对齐
 */

/** Agent 状态 */
export type AgentStatus = 'draft' | 'published'

/** Agent 种类 */
export type AgentType = 'agent' | 'flow' | 'persona'

/** Agent 实例 */
export interface Agent {
  id: string
  name: string
  description: string
  status: AgentStatus
  agent_type: AgentType
  /** 绑定的主模型展示名 */
  model_display_name?: string
  /** 绑定的工具数 */
  tool_count: number
  /** 绑定的知识库数 */
  knowledge_count: number
  created_at: string
  updated_at: string
}
