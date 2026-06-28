/**
 * MCP server API — 对接 backend/app/api/routes/mcp/*
 *
 * 路径前缀 `/mcp-servers`，加上 axios baseURL `/api/v1`。
 */

import { del, get, post, put } from '@/request'
import type { MCPServer, MCPTransport } from '@/types'

export interface MCPServerCreatePayload {
  name: string
  server_url: string
  transport?: MCPTransport
  /** 自定义请求头（含鉴权 token，明文提交，后端加密存储） */
  headers?: Record<string, string>
  description?: string
  enabled?: boolean
}

export interface MCPServerUpdatePayload {
  name?: string
  server_url?: string
  transport?: MCPTransport
  /** 新请求头，留空（不传）则不改 */
  headers?: Record<string, string>
  description?: string
  enabled?: boolean
}

/** 列出当前用户的 MCP server。 */
export function listMCPServers() {
  return get<MCPServer[]>('/mcp-servers')
}

/** 创建 MCP server。走 silent 由表单层 toast，方便显示后端具体原因。 */
export function createMCPServer(payload: MCPServerCreatePayload) {
  return post<MCPServer>('/mcp-servers', payload, { silent: true })
}

/** 更新 MCP server（部分字段；启用开关切换也走这里）。 */
export function updateMCPServer(id: string, payload: MCPServerUpdatePayload) {
  return put<MCPServer>(`/mcp-servers/${id}`, payload)
}

/** 删除 MCP server。 */
export function deleteMCPServer(id: string) {
  return del<null>(`/mcp-servers/${id}`)
}

export interface MCPTestConnectionPayload {
  server_url: string
  transport?: MCPTransport
  headers?: Record<string, string>
}

export interface MCPToolBrief {
  name: string
  description: string
}

export interface MCPTestConnectionResult {
  success: boolean
  tool_count: number
  tools: MCPToolBrief[]
  error: string | null
}

/**
 * 测试连接：用配置直接试连 MCP server，返回连通性 + 发现的工具列表。
 *
 * 后端把「连不上」当正常业务结果（success=false + error），不抛 HTTP 错误；
 * 走 silent 由弹窗内联展示结果。
 */
export function testMCPConnection(payload: MCPTestConnectionPayload) {
  return post<MCPTestConnectionResult>('/mcp-servers/test', payload, {
    silent: true,
  })
}
