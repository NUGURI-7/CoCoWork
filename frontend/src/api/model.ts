/**
 * Model API — 对接 backend/app/api/routes/model/*
 *
 * 路径前缀 `/providers` / `/models`，加上 axios baseURL `/api/v1`。
 */

import { del, get, post } from '@/request'
import type {
  AIModel,
  CatalogItem,
  ModelType,
  ModelTypeParams,
  Provider,
  ProviderType,
} from '@/types'

// ============================================================================
// Provider
// ============================================================================

export interface ProviderCreatePayload {
  name: string
  provider_type: ProviderType
  base_url: string
  api_key: string
  description?: string
}

/** 列出当前用户的 Provider 列表。 */
export function listProviders() {
  return get<Provider[]>('/providers')
}

/**
 * 创建 Provider。
 *
 * 后端会在创建时做连通性验证（base_url + api_key），失败则不入库并返回业务错误。
 * 走 silent 由表单层 toast，方便显示后端具体原因。
 */
export function createProvider(payload: ProviderCreatePayload) {
  return post<Provider>('/providers', payload, { silent: true })
}

/** 删除 Provider。 */
export function deleteProvider(id: string) {
  return del<null>(`/providers/${id}`)
}

// ============================================================================
// AIModel
// ============================================================================

/**
 * AIModel 创建 payload。
 *
 * `provider_id` 不在 body —— 由 URL path 提供（`createModel(providerId, ...)`），
 * 跟后端 schema 一致避免双源歧义。
 */
export interface ModelCreatePayload {
  model_name: string
  display_name: string
  model_type: ModelType
  config?: Record<string, unknown>
  base_url?: string | null
  api_key?: string | null
  is_enabled?: boolean
}

interface ListModelsFilter {
  modelType?: ModelType
  enabledOnly?: boolean
}

function buildModelQuery(filter?: ListModelsFilter) {
  const query: Record<string, string | boolean> = {}
  if (filter?.modelType) query.model_type = filter.modelType
  if (filter?.enabledOnly) query.enabled_only = true
  return Object.keys(query).length ? query : undefined
}

/** 列出某 Provider 下的 AIModel（nested 端点）。 */
export function listModelsByProvider(
  providerId: string,
  filter?: ListModelsFilter,
) {
  return get<AIModel[]>(
    `/providers/${providerId}/models`,
    buildModelQuery(filter),
  )
}

/**
 * 跨 Provider 列出当前用户所有 AIModel（flat 端点）。
 *
 * 典型场景：建知识库时挑选 embedding 模型，不限 provider。
 */
export function listAllModels(filter?: ListModelsFilter) {
  return get<AIModel[]>('/models', buildModelQuery(filter))
}

/**
 * 在指定 Provider 下创建 AIModel。
 *
 * 后端会做连通性验证，失败则不入库。走 silent 由表单层 toast。
 */
export function createModel(providerId: string, payload: ModelCreatePayload) {
  return post<AIModel>(`/providers/${providerId}/models`, payload, { silent: true })
}

/** 删除 AIModel。 */
export function deleteModel(providerId: string, modelId: string) {
  return del<null>(`/providers/${providerId}/models/${modelId}`)
}

/** 获取参数定义（按 model_type 索引）。 */
export function getParamDefinitions() {
  return get<Record<string, ModelTypeParams>>('/models/param-definitions')
}

// ============================================================================
// Catalog
// ============================================================================

/** 查询模型目录（按 provider_type 过滤）。 */
export function listCatalog(providerType?: ProviderType) {
  return get<CatalogItem[]>(
    '/catalog',
    providerType ? { provider_type: providerType } : undefined,
  )
}

export interface CatalogCreatePayload {
  provider_type: ProviderType
  model_id: string
  model_type: ModelType
}

/** 添加目录条目（需 admin）。走 silent 由表单层 toast。 */
export function createCatalog(payload: CatalogCreatePayload) {
  return post<CatalogItem>('/catalog', payload, { silent: true })
}

/** 删除目录条目（需 admin）。 */
export function deleteCatalog(id: string) {
  return del<null>(`/catalog/${id}`)
}
