/**
 * Tool API — 对接 backend/app/api/routes/tool/*
 *
 * 路径前缀 `/tools`，加上 axios baseURL `/api/v1`。
 */

import { get } from '@/request'
import type { Tool } from '@/types'

/** 列出当前可装配的工具（内置；未来含 MCP / custom）。 */
export function listTools() {
  return get<Tool[]>('/tools')
}
