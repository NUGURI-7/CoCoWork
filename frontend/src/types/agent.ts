/**
 * Agent 模块类型 — 对齐 backend/app/schemas/agent/config_schema.py
 *
 * Hybrid Schema：核心列（name/description/template）+ config jsonb（强类型契约）。
 * config 嵌套结构跟后端 AgentConfig Pydantic 1:1。
 */

/** 模板分类——对齐后端 LoopTemplate / GraphTemplate 二分 */
export type TemplateKind = 'loop' | 'graph'

/** 行为模板枚举（mock 兼容，workspace 仍在用） */
export type BehaviorType = 'single' | 'supervisor' | 'pipeline' | 'react'

/** 模板（平台预置；后端目前未暴露列表端点，前端先用占位） */
export interface Template {
  /** 后端 registry key（创建 Agent 时透传到 AgentCreate.template） */
  key: string
  /** 显示名 */
  name: string
  /** 模板分类（Loop 引擎 / Graph 编排） */
  kind: TemplateKind
  /** 一句话描述 */
  description: string
  /** 后端未实装 → 占位展示 disabled */
  disabled?: boolean
  /** 可选：mock 数据 id（早期遗留，CreateAgentDialog / RecruitDialog 还在用） */
  id?: string
  /** 可选：Lucide 图标名（CreateAgentDialog / TemplateCard 用） */
  icon?: string
}

// ============ AgentConfig（对齐后端 schemas/agent/config_schema.py） ============

/**
 * 模型槽位调用参数（chat / tts / stt 各槽位独立）。
 *
 * 后端 ModelParams extra="allow" —— 透传 response_format / stop / seed 等扩展
 * 参数给 LangChain init_chat_model。前端 index signature 兜底类型。
 */
export interface ModelParams {
  temperature?: number | null
  top_p?: number | null
  max_tokens?: number | null
  /**
   * 思考档位（off / low / high / max）；缺省或 null = 不传，由模型自己的默认决定。
   * 不是原样透传的参数 —— 后端会翻译成各家上游的方言。
   */
  reasoning_effort?: string | null
  [key: string]: unknown
}

/** 一个能力槽位的模型引用 + 调用参数。 */
export interface ModelSlot {
  id: string
  params: ModelParams
}

/**
 * 按能力的模型组合 —— 单模型多模态（chat 槽位）+ 多模型组合（stt/tts/vision/...）。
 *
 * P0 只用 chat；其他槽位等 voice / vision 那片实装时启用。
 */
export interface AgentModels {
  chat?: ModelSlot | null
  stt?: ModelSlot | null
  tts?: ModelSlot | null
  vision?: ModelSlot | null
  image_gen?: ModelSlot | null
  video?: ModelSlot | null
}

/** 产品层行为配置（voice agent VAD / 打断阈值 / turn detection 等，P0 空）。 */
export interface AgentBehavior {
  // 留口，后端 extra="forbid" 严格
}

/** UI 元数据（跟运行解耦，前端展示用）。 */
export interface AgentUI {
  /** 用户上传的头像 URL；P0 不暴露上传 UI、前端 fallback 到默认 png */
  avatar_url?: string | null
}

export interface AgentConfig {
  models?: AgentModels
  system_prompt?: string | null
  capabilities?: string[]
  knowledge?: string[]
  builtin_tools?: string[]
  /** MCP server，按 id 挂载（运行时连上去拉工具） */
  mcp_servers?: string[]
  /** 用户上传的 skill，按 id 挂载（DB 实体，本体在对象存储） */
  skills?: string[]
  /** 内置 skill，按 name 挂载（本体随代码分发、不进表，同 builtin_tools 的形态） */
  builtin_skills?: string[]
  behavior?: AgentBehavior
  ui?: AgentUI
}

/** Agent 主体（后端 AgentOut 1:1）。 */
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

/**
 * 旧版 Playground 用过的对话消息形态（已迁移到 chat-store 的 ChatMessage）。
 * 保留兼容，types/index.ts 仍 re-export，避免下游引用断链。
 */
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}
