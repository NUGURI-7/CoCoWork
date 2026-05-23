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
  is_global: boolean
  is_enabled: boolean
  /** 已创建的模型数（聚合字段，后端返回） */
  model_count?: number
  created_at: string
  updated_at: string
}

/** AIModel 模型实例（已创建） */
export interface AIModel {
  id: string
  provider_id: string
  model_name: string
  display_name: string
  model_type: ModelType
  config: Record<string, unknown>
  is_enabled: boolean
  created_at: string
  updated_at: string
}

/** 上游可用模型（连通性测试返回） */
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
