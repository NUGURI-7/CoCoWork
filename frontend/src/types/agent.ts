/**
 * Agent 模块类型 — 对齐 docs/design/agent-module-v1.md
 * 三层分离：模板（平台预置，前端只读）/ Agent（用户资产）/ 实例（工作空间内成员，v2+）
 */

/** 行为模板枚举（LangGraph 行为骨架） */
export type BehaviorType = 'single' | 'supervisor' | 'pipeline' | 'react'

/** 模板（平台预置的纯行为骨架空壳，用户不可建不可改） */
export interface Template {
  id: string
  /** 显示名（"研究员"/"写手"） */
  name: string
  behavior_type: BehaviorType
  /** 一句话描述 */
  description: string
  /** Lucide 图标名（"Search"/"PenTool"），渲染时用 dynamic import 或 icon map */
  icon: string
  /** 基于此模板创建 Agent 时的默认头像底色（hex） */
  default_avatar_color: string
}

/** Agent 调用参数（temperature/top_p/max_tokens 等，结构松散允许未来扩展） */
export interface AgentConfig {
  temperature?: number
  top_p?: number
  max_tokens?: number
}

/** Agent（用户基于模板装备的资产） */
export interface Agent {
  id: string
  /** 用户起的名 */
  name: string
  template_id: string
  /** 冗余，省得每次 join（前端只用） */
  template_name: string
  /** 从模板带过来，只读展示 */
  behavior_type: BehaviorType
  /** 创建时从模板默认色继承，可改 */
  avatar_color: string
  /** 用户自填 */
  description: string
  /** 必填业务上，mock 允许 null（裸 Agent 验空态） */
  model_id: string | null
  model_display_name: string | null
  /** 非必填，留空 = 使用模板默认行为 */
  system_prompt: string | null
  config: AgentConfig
  knowledge_ids: string[]
  tool_ids: string[]
  mcp_ids: string[]
  created_at: string
  updated_at: string
}

/** 详情页右栏对话消息（v0 mock，本地 state） */
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}
