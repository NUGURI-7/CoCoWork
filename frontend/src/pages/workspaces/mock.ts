/** Mock 数据 — 后端切片 4+ 就绪后删除（v0 纯前端 local state，仅为画 UI） */

import { v4 as uuidv4 } from 'uuid'

import type { Workspace, WorkspaceMember } from '@/types'

/** 每个空间固定的管家成员（supervisor） */
function supervisor(): WorkspaceMember {
  return {
    id: uuidv4(),
    name: '管家',
    role: 'supervisor',
    source: 'template',
    source_name: '调度',
    behavior_type: 'supervisor',
  }
}

export const mockWorkspaces: Workspace[] = [
  {
    id: 'ws-phd-thesis',
    name: '博士论文项目',
    description: '文献调研 + 写作 + 校对的长期协作空间',
    members: [
      supervisor(),
      {
        id: 'wm-researcher',
        name: '研究员',
        role: 'agent',
        source: 'template',
        source_name: '研究员',
        behavior_type: 'single',
      },
      {
        id: 'wm-writer',
        name: '学术写手',
        role: 'agent',
        source: 'agent',
        source_name: '营销文案手',
        behavior_type: 'single',
      },
      {
        id: 'wm-proofreader',
        name: '校对',
        role: 'agent',
        source: 'template',
        source_name: '校对',
        behavior_type: 'single',
      },
    ],
    conversations: [
      {
        id: 'conv-phd-1',
        title: '文献调研讨论',
        created_at: '2026-05-15T10:00:00Z',
        updated_at: '2026-05-27T14:30:00Z',
      },
      {
        id: 'conv-phd-2',
        title: '第三章写作',
        created_at: '2026-05-22T09:00:00Z',
        updated_at: '2026-05-26T11:20:00Z',
      },
    ],
    created_at: '2026-05-15T10:00:00Z',
    updated_at: '2026-05-27T14:30:00Z',
  },
  {
    id: 'ws-product-launch',
    name: '新品发布筹备',
    description: '营销文案 + 数据分析协同，产出发布物料',
    members: [
      supervisor(),
      {
        id: 'wm-marketing',
        name: '文案手',
        role: 'agent',
        source: 'agent',
        source_name: '营销文案手',
        behavior_type: 'single',
      },
      {
        id: 'wm-analyst',
        name: '数据分析师',
        role: 'agent',
        source: 'template',
        source_name: '数据分析师',
        behavior_type: 'pipeline',
      },
    ],
    conversations: [
      {
        id: 'conv-launch-1',
        title: '文案初稿',
        created_at: '2026-05-20T09:00:00Z',
        updated_at: '2026-05-26T18:00:00Z',
      },
    ],
    created_at: '2026-05-20T09:00:00Z',
    updated_at: '2026-05-26T18:00:00Z',
  },
  {
    id: 'ws-empty',
    name: '空白空间',
    description: '',
    members: [supervisor()],
    conversations: [
      {
        id: 'conv-empty-1',
        title: '新对话',
        created_at: '2026-05-26T10:00:00Z',
        updated_at: '2026-05-26T10:00:00Z',
      },
    ],
    created_at: '2026-05-26T10:00:00Z',
    updated_at: '2026-05-26T10:00:00Z',
  },
]
