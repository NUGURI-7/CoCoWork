/** 工具列表静态 mock（不接 API）；字段按未来后端模型预埋 */

import {
  BookOpen,
  Calculator,
  Clock,
  Database,
  FolderOpen,
  Github,
  Globe,
  Link2,
  type LucideIcon,
} from 'lucide-react'

/** 工具来源：内置（代码维护）/ MCP（管理员接入的 server 暴露） */
export type ToolSource = 'builtin' | 'mcp'

export interface Tool {
  id: string
  name: string
  description: string
  source: ToolSource
  icon: LucideIcon
  enabled: boolean
  /** MCP 来源 server 名（source = 'mcp' 时有值） */
  server?: string
}

export const mockTools: Tool[] = [
  // 内置
  {
    id: 'b1',
    name: '联网搜索',
    description: '通过搜索引擎获取实时网络信息，返回标题、摘要与链接。',
    source: 'builtin',
    icon: Globe,
    enabled: true,
  },
  {
    id: 'b2',
    name: '知识库检索',
    description: '在指定知识库中做语义检索，返回最相关的段落与来源。',
    source: 'builtin',
    icon: BookOpen,
    enabled: true,
  },
  {
    id: 'b3',
    name: '网页抓取',
    description: '抓取并解析指定 URL 的网页正文，转成纯文本。',
    source: 'builtin',
    icon: Link2,
    enabled: false,
  },
  {
    id: 'b4',
    name: '计算器',
    description: '执行数学表达式计算，支持四则运算与常用函数。',
    source: 'builtin',
    icon: Calculator,
    enabled: true,
  },
  {
    id: 'b5',
    name: '当前时间',
    description: '获取当前日期与时间，可指定时区。',
    source: 'builtin',
    icon: Clock,
    enabled: true,
  },
  // MCP（管理员接入的 server 暴露的 tool，平铺到 tool 级）
  {
    id: 'm1',
    name: '创建 Issue',
    description: '在指定仓库下创建一个新的 GitHub Issue。',
    source: 'mcp',
    icon: Github,
    enabled: true,
    server: 'GitHub',
  },
  {
    id: 'm2',
    name: '搜索仓库',
    description: '按关键词搜索 GitHub 仓库，返回名称、描述与 star 数。',
    source: 'mcp',
    icon: Github,
    enabled: false,
    server: 'GitHub',
  },
  {
    id: 'm3',
    name: '读取文件',
    description: '读取本地文件系统中指定路径的文件内容。',
    source: 'mcp',
    icon: FolderOpen,
    enabled: true,
    server: 'Filesystem',
  },
  {
    id: 'm4',
    name: '执行查询',
    description: '在 Postgres 数据库上执行只读 SQL 查询并返回结果。',
    source: 'mcp',
    icon: Database,
    enabled: false,
    server: 'Postgres',
  },
]

/** 来源徽标元数据 */
export const sourceMeta: Record<ToolSource, { label: string }> = {
  builtin: { label: '内置' },
  mcp: { label: 'MCP' },
}
