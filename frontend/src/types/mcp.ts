/**
 * MCP server 模块类型 — 对齐 backend/app/schemas/mcp/mcp_schema.py。
 *
 * MCPServer 对应 MCPServerOut：不含 headers（鉴权头加密存储、不回传）。
 */

export type MCPTransport = 'streamable_http' | 'sse'

/** 用户配置的外部 MCP server（Client 侧）。 */
export interface MCPServer {
  id: string
  name: string
  server_url: string
  transport: MCPTransport
  description: string
  enabled: boolean
  created_at: string
  updated_at: string
}
