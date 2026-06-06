/**
 * Mock 数据 — 模板池 + ConfigPanel 工具列表占位。
 *
 * **模板池**：后端 registry v1 只有 `builtin/general` 一个 loop 引擎，所以这里只放
 * 1 张真模板 + 1 张 graph 占位（disabled）。等后端暴露 `GET /agents/templates`
 * 端点后，整张表从 API 拉。
 *
 * **工具列表**：后端 tool 模块尚未起，先保留 mock；chat 模型 / 知识库已经接真接口。
 */

import type { Template } from '@/types'

/** 工具 mock 形态（暂无正式 tool 类型，先在此就地定义） */
export interface ToolMock {
  id: string
  name: string
  type: 'builtin' | 'mcp'
  /** Lucide icon 名 */
  icon: string
}

// ─── 模板池（1 真 + 1 假占位） ─────────────────────────────────────

export const mockTemplates: Template[] = [
  {
    id: 't-general-loop',
    key: 'general',
    name: '通用 Loop',
    kind: 'loop',
    description: '可装备模型、知识库、工具的通用单 Agent 引擎',
    icon: 'Bot',
  },
  {
    id: 't-mock-graph',
    key: '__mock__/graph_demo',
    name: '示例 Graph',
    kind: 'graph',
    description: 'Graph 形态占位（多节点编排，敬请期待）',
    icon: 'Workflow',
    disabled: true,
  },
]

// ─── 工具（3 个） ────────────────────────────────────────────────────

export const mockTools: ToolMock[] = [
  { id: 'tool-web-search', name: '联网搜索', type: 'builtin', icon: 'Globe' },
  { id: 'tool-code-runner', name: '代码执行', type: 'builtin', icon: 'Terminal' },
  { id: 'tool-mcp-figma', name: 'Figma MCP', type: 'mcp', icon: 'Figma' },
]

