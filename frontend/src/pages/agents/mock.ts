/**
 * Mock 数据 — 模板池 + ConfigPanel 用的资源占位（chat 模型 / 知识库 / 工具）。
 *
 * **模板池**：后端 registry v1 只有 `builtin/general` 一个 loop 引擎，所以这里只放
 * 1 张真模板 + 1 张 graph 占位（disabled）。等后端暴露 `GET /agents/templates`
 * 端点后，整张表从 API 拉。
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

/** Chat 模型 mock（轻量，只放 Select 用得到的字段；对齐 types/model.ts 的 AIModel 子集） */
export interface ChatModelMock {
  id: string
  display_name: string
}

/** 知识库 mock（轻量，只放 agent 关联场景用得到的字段） */
export interface KnowledgeMock {
  id: string
  name: string
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
    default_avatar_color: '#2f6b53',
  },
  {
    id: 't-mock-graph',
    key: '__mock__/graph_demo',
    name: '示例 Graph',
    kind: 'graph',
    description: 'Graph 形态占位（多节点编排，敬请期待）',
    icon: 'Workflow',
    default_avatar_color: '#a855f7',
    disabled: true,
  },
]

// ─── Chat 模型（4 个） ───────────────────────────────────────────────

export const mockChatModels: ChatModelMock[] = [
  { id: 'm-gpt-4', display_name: 'GPT-4' },
  { id: 'm-qwen-plus', display_name: 'Qwen Plus' },
  { id: 'm-deepseek-chat', display_name: 'DeepSeek Chat' },
  { id: 'm-claude-sonnet', display_name: 'Claude Sonnet' },
]

// ─── 知识库（3 个） ──────────────────────────────────────────────────

export const mockKnowledge: KnowledgeMock[] = [
  { id: 'kb-internal-api', name: '内部 API 文档' },
  { id: 'kb-brand-words', name: '品牌词库' },
  { id: 'kb-product-spec', name: '产品规格手册' },
]

// ─── 工具（3 个） ────────────────────────────────────────────────────

export const mockTools: ToolMock[] = [
  { id: 'tool-web-search', name: '联网搜索', type: 'builtin', icon: 'Globe' },
  { id: 'tool-code-runner', name: '代码执行', type: 'builtin', icon: 'Terminal' },
  { id: 'tool-mcp-figma', name: 'Figma MCP', type: 'mcp', icon: 'Figma' },
]

