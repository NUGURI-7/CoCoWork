/**
 * Model 模块类型 — 对齐 backend/app/models/provider_model.py + ai_model.py
 */

/** 供应商类型枚举 */
export type ProviderType =
  | 'openai'
  | 'dashscope'
  | 'siliconflow'
  | 'deepseek'
  | 'anthropic'
  | 'custom'

/** 模型类型枚举 */
export type ModelType =
  | 'chat'
  | 'embedding'
  | 'rerank'
  | 'vision'
  | 'tts'
  | 'stt'
  | 'image'
  | 'multimodal'

/**
 * 凭证字段定义（对齐后端 CredentialField）。
 *
 * 各家供应商要填的凭证不同（OpenAI 一个 api_key、百度要 api_key + secret_key），
 * 由后端 `/providers/credential-definitions` 下发，表单据此渲染，不在前端写死。
 */
export interface CredentialField {
  key: string
  label: string
  /** 是否敏感字段：true 渲染成密码框 */
  secret: boolean
  required: boolean
}

/** 参数字段定义（对齐后端 ParamField） */
export interface ParamField {
  key: string
  label: string
  type: 'number' | 'slider' | 'switch'
  min?: number
  max?: number
  step?: number
  default?: number | boolean | null
  description?: string
}

/** 某个 model_type 的参数定义集 */
export interface ModelTypeParams {
  config_fields: ParamField[]
  invocation_params: ParamField[]
}

/** Provider 供应商实例 */
export interface Provider {
  id: string
  name: string
  provider_type: ProviderType
  base_url: string
  description: string
  created_at: string
  updated_at: string
}

/** AIModel 模型实例（已创建） */
export interface AIModel {
  id: string
  model_name: string
  display_name: string
  model_type: ModelType
  config: Record<string, unknown>
  /** 类型相关元数据：embedding 模型带 embedding_dim */
  meta?: { embedding_dim?: number } | null
  has_custom_base_url: boolean
  has_custom_credentials: boolean
  is_enabled: boolean
  created_at: string
  updated_at: string
}

/** Catalog 目录条目（管理员维护的可用模型清单） */
export interface CatalogItem {
  id: string
  provider_type: ProviderType
  model_id: string
  model_type: ModelType
}

/** 上游可用模型（按类型分组后用于 UI 渲染） */
export interface AvailableModel {
  model_name: string
  model_type?: ModelType
}

/** 按类型分组后的可用模型 */
export interface AvailableModelGroup {
  type: ModelType
  label: string
  models: AvailableModel[]
}
