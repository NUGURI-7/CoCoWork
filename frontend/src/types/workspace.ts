/**
 * Workspace 模块类型 — 对齐 docs/design/agent-module-v1.md §5
 *
 * ⚠️ v0 画图占位形态，非正式 schema。后端切片 4+ 出真接口时照着重写。
 * 成员（实例）直接内嵌进 Workspace，画 UI 方便；正式版会拆 member 表 + 注入字段。
 */

import type { BehaviorType } from './agent'

/** 工作空间成员（= spec 里的 Agent 实例的前端简化形态） */
export interface WorkspaceMember {
  id: string
  /** 实例在该空间的显示名 */
  name: string
  /** 头像底色（hex），从源模板/Agent 继承 */
  avatar_color: string
  /** 管家固定一个，其余都是 agent */
  role: 'supervisor' | 'agent'
  /** 来源：招毛坯模板 or 招用户已建的 Agent */
  source: 'template' | 'agent'
  /** 来源名（"研究员" / "营销文案手"），UI 标注用 */
  source_name: string
  behavior_type: BehaviorType
}

/** 对话（v0 只存元数据，messages 仍走组件内存） */
export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

/** 工作空间 */
export interface Workspace {
  id: string
  name: string
  description: string
  /** 内嵌成员（含管家），画卡片头像堆叠 + 详情通讯录共用 */
  members: WorkspaceMember[]
  /** 该空间的对话历史（按 updated_at 倒序展示） */
  conversations: Conversation[]
  created_at: string
  updated_at: string
}
