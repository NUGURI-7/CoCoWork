/** Mock 数据 — 后端 API 就绪后删除（v0 切片 0，纯前端 local state） */

import type { Agent, Template } from '@/types'

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

// ─── 模板池（8 个，平台预置） ───────────────────────────────────────

export const mockTemplates: Template[] = [
  {
    id: 't-researcher',
    name: '研究员',
    behavior_type: 'single',
    description: '信息检索、文献查阅、要点归纳',
    icon: 'Search',
    default_avatar_color: '#2f6b53',
  },
  {
    id: 't-writer',
    name: '写手',
    behavior_type: 'single',
    description: '文字创作、文案润色、风格调整',
    icon: 'PenTool',
    default_avatar_color: '#7c5cff',
  },
  {
    id: 't-proofreader',
    name: '校对',
    behavior_type: 'single',
    description: '语法校对、事实核查、逻辑审视',
    icon: 'ClipboardCheck',
    default_avatar_color: '#0ea5e9',
  },
  {
    id: 't-investigator',
    name: '调查员',
    behavior_type: 'react',
    description: '主动多轮查找、对比、追问',
    icon: 'Telescope',
    default_avatar_color: '#f59e0b',
  },
  {
    id: 't-translator',
    name: '翻译',
    behavior_type: 'single',
    description: '多语种翻译，保持术语一致',
    icon: 'Languages',
    default_avatar_color: '#10b981',
  },
  {
    id: 't-data-analyst',
    name: '数据分析师',
    behavior_type: 'pipeline',
    description: '数据清洗、统计、可视化建议',
    icon: 'BarChart3',
    default_avatar_color: '#3b82f6',
  },
  {
    id: 't-code-assistant',
    name: '编程助手',
    behavior_type: 'react',
    description: '代码理解、调试、解释',
    icon: 'Code2',
    default_avatar_color: '#ef4444',
  },
  {
    id: 't-product-manager',
    name: '产品经理',
    behavior_type: 'supervisor',
    description: '需求拆解、用户故事编写',
    icon: 'LayoutDashboard',
    default_avatar_color: '#a855f7',
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

// ─── 我的 Agent（5 个，含一个裸 Agent 验空态） ──────────────────────

export const mockAgents: Agent[] = [
  {
    id: 'a-code-researcher',
    name: '代码研究员',
    template_id: 't-code-assistant',
    template_name: '编程助手',
    behavior_type: 'react',
    avatar_color: '#ef4444',
    description: '读内部仓库 + 解释代码 + 帮排查 bug',
    model_id: 'm-claude-sonnet',
    model_display_name: 'Claude Sonnet',
    system_prompt: '你是一名熟悉内部代码库的资深工程师，回答以引用源码为准。',
    config: { temperature: 0.3, top_p: 1, max_tokens: 2048 },
    knowledge_ids: ['kb-internal-api'],
    tool_ids: ['tool-web-search', 'tool-code-runner'],
    mcp_ids: [],
    created_at: '2026-05-18T10:00:00Z',
    updated_at: '2026-05-25T14:30:00Z',
  },
  {
    id: 'a-marketing-writer',
    name: '营销文案手',
    template_id: 't-writer',
    template_name: '写手',
    behavior_type: 'single',
    avatar_color: '#7c5cff',
    description: '按品牌调性产出落地页文案、社媒推文',
    model_id: 'm-gpt-4',
    model_display_name: 'GPT-4',
    system_prompt: '你写文案要紧贴品牌词库里的术语，避免空泛形容词。',
    config: { temperature: 0.9, top_p: 1, max_tokens: 1024 },
    knowledge_ids: ['kb-brand-words'],
    tool_ids: [],
    mcp_ids: [],
    created_at: '2026-05-19T09:00:00Z',
    updated_at: '2026-05-23T16:00:00Z',
  },
  {
    id: 'a-paper-translator',
    name: '论文翻译',
    template_id: 't-translator',
    template_name: '翻译',
    behavior_type: 'single',
    avatar_color: '#10b981',
    description: '中英学术论文互译，保留专业术语',
    model_id: 'm-qwen-plus',
    model_display_name: 'Qwen Plus',
    system_prompt: null,
    config: { temperature: 0.2, top_p: 1, max_tokens: 4096 },
    knowledge_ids: [],
    tool_ids: [],
    mcp_ids: [],
    created_at: '2026-05-20T11:00:00Z',
    updated_at: '2026-05-22T09:00:00Z',
  },
  {
    id: 'a-weekly-report',
    name: '周报生成',
    template_id: 't-product-manager',
    template_name: '产品经理',
    behavior_type: 'supervisor',
    avatar_color: '#a855f7',
    description: '从项目动态汇总成结构化周报',
    model_id: 'm-deepseek-chat',
    model_display_name: 'DeepSeek Chat',
    system_prompt: '产出格式：本周完成 / 下周计划 / 风险与阻塞。',
    config: { temperature: 0.5, top_p: 1, max_tokens: 1536 },
    knowledge_ids: ['kb-product-spec'],
    tool_ids: [],
    mcp_ids: [],
    created_at: '2026-05-21T08:00:00Z',
    updated_at: '2026-05-24T18:00:00Z',
  },
  {
    id: 'a-naked',
    name: '裸 Agent',
    template_id: 't-researcher',
    template_name: '研究员',
    behavior_type: 'single',
    avatar_color: '#2f6b53',
    description: '',
    model_id: null,
    model_display_name: null,
    system_prompt: null,
    config: {},
    knowledge_ids: [],
    tool_ids: [],
    mcp_ids: [],
    created_at: '2026-05-26T10:00:00Z',
    updated_at: '2026-05-26T10:00:00Z',
  },
]
