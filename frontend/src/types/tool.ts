/**
 * Tool 模块类型 — 对齐 backend/app/schemas/tool/tool_schema.py（ToolOut）。
 *
 * 这几个字段所有工具来源（内置 / MCP / custom）天生都有，新增来源套同一结构。
 */

export type ToolSource = 'builtin' | 'mcp' | 'custom'

export interface Tool {
  /** registry key，勾选后写进 config.builtin_tools */
  name: string
  /** 中文展示名 */
  display_name: string
  /** 能力描述 */
  description: string
  /** 来源，前端按此分组 */
  source_type: ToolSource
  /** 有副作用（删文件 / 发请求 / 花钱）标记 */
  dangerous: boolean
}
