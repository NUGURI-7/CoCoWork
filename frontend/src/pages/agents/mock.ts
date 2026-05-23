/** Mock 数据 — 后端 API 就绪后删除 */

import type { Agent } from '@/types'

export const mockAgents: Agent[] = [
  {
    id: 'a1',
    name: '客服助手',
    description: '处理客户常见问题，支持退换货咨询、订单查询和售后服务',
    status: 'published',
    agent_type: 'agent',
    model_display_name: 'Qwen Plus',
    tool_count: 3,
    knowledge_count: 2,
    created_at: '2026-05-18T10:00:00Z',
    updated_at: '2026-05-22T14:30:00Z',
  },
  {
    id: 'a2',
    name: '文档分析师',
    description: '基于上传的文档进行内容提取、摘要和问答',
    status: 'published',
    agent_type: 'agent',
    model_display_name: 'Qwen Max',
    tool_count: 1,
    knowledge_count: 4,
    created_at: '2026-05-19T09:00:00Z',
    updated_at: '2026-05-21T16:00:00Z',
  },
  {
    id: 'a3',
    name: '研究助理',
    description: '多步骤研究任务：搜索、整理、分析、生成报告',
    status: 'draft',
    agent_type: 'flow',
    model_display_name: 'DeepSeek Chat',
    tool_count: 5,
    knowledge_count: 0,
    created_at: '2026-05-20T11:00:00Z',
    updated_at: '2026-05-23T09:00:00Z',
  },
  {
    id: 'a4',
    name: '代码审查',
    description: '自动审查代码变更，检查风格、安全性和性能问题',
    status: 'draft',
    agent_type: 'persona',
    model_display_name: 'Qwen Turbo',
    tool_count: 2,
    knowledge_count: 1,
    created_at: '2026-05-22T08:00:00Z',
    updated_at: '2026-05-22T08:00:00Z',
  },
]
