/**
 * Tool 模块类型 — 对齐 backend/app/schemas/tool/tool_schema.py（ToolOut）。
 *
 * 这几个字段所有工具来源（内置 / MCP / custom）天生都有，新增来源套同一结构。
 */

export type ToolSource = 'builtin' | 'mcp' | 'custom'

/**
 * 能力分类 — 对齐后端 `app/tools/base.py` 的 ToolCategory。
 *
 * 按能力分而非按主题分（不是 search / weather / finance 那种）：卡片上的标签，
 * 同时也是模板配置校验的判据（「有没有挂能查到外部信息的工具」）。
 */
export type ToolCategory = 'data_source' | 'utility'

export interface Tool {
  /** registry key，勾选后写进 config.builtin_tools */
  name: string
  /** 中文展示名 */
  display_name: string
  /** 能力描述 */
  description: string
  /** 来源，前端按此分组 */
  source_type: ToolSource
  /** 能力分类，卡片上的标签 */
  category: ToolCategory
  /** 有副作用（删文件 / 发请求 / 花钱）标记 */
  dangerous: boolean
}
