/**
 * Agent 模块类型 — 对齐 backend/app/schemas/agent/agent_schema.py
 *
 * 后端 `AgentOut` 走 Hybrid Schema：核心列（name/description/template）+ `config` jsonb。
 * 前端 `Agent` 跟后端 1:1；模板时代的扁平字段（model_id / system_prompt / knowledge_ids ...）
 * 全部下沉到 `config` 里，下一口接入组件时再细化 `AgentConfig` 的形状。
 */

/** 行为模板枚举（mock 兼容，workspace 仍在用） */
export type BehaviorType = 'single' | 'supervisor' | 'pipeline' | 'react'

/** 模板分类——对齐后端 `LoopTemplate` / `GraphTemplate` 二分 */
export type TemplateKind = 'loop' | 'graph'

/** 模板（平台预置的行为骨架空壳，用户不可建不可改；后端目前未暴露列表端点，前端先用占位） */
export interface Template {
  id: string
  /** 后端 registry key（创建 Agent 时透传到 `AgentCreate.template`） */
  key: string
  /** 显示名（"通用 Loop"） */
  name: string
  /** 模板分类（Loop 引擎 / Graph 编排） */
  kind: TemplateKind
  /** 一句话描述 */
  description: string
  /** Lucide 图标名（"Search"/"PenTool"），渲染时用 dynamic import 或 icon map */
  icon: string
  /** 基于此模板创建 Agent 时的默认头像底色（hex） */
  default_avatar_color: string
  /** 真假标识——`true` 表示后端尚未实装，前端只做占位展示、不可选 */
  disabled?: boolean
}

/**
 * Agent 配置（后端 jsonb，宽松形状）。
 *
 * 约定字段（v1，可逐步细化）：
 *   - `model_id`           当前使用的 AIModel id
 *   - `system_prompt`      系统提示词
 *   - `knowledge_ids`      挂载的知识库 id 列表
 *   - `tool_ids`           挂载的内置工具 id 列表
 *   - `mcp_ids`            挂载的 MCP 工具 id 列表
 *   - `avatar_color`       头像底色（hex）
 *   - `params`             调用参数（temperature/top_p/max_tokens 等）
 *
 * 未列出的字段也可写入（jsonb 不校验），便于演进。
 */
export interface AgentConfig {
  model_id?: string | null
  system_prompt?: string | null
  knowledge_ids?: string[]
  tool_ids?: string[]
  mcp_ids?: string[]
  avatar_color?: string
  params?: {
    temperature?: number
    top_p?: number
    max_tokens?: number
  }
  [key: string]: unknown
}

/** Agent（后端 `AgentOut` 直映射） */
export interface Agent {
  id: string
  name: string
  description: string
  /** 引用的内置模板 registry key，创建后锁死 */
  template: string
  config: AgentConfig
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
