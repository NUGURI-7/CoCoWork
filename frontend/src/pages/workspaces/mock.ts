/**
 * Mock 成员形态 — d-2 member / 招募接真前，通讯录 / 招募弹窗 / @mention UI 用。
 *
 * workspace / conversation 的 mock 形态已退役（3b / 3c-2 接真）；
 * 本文件只剩成员一脉，d-2 招募片接真后整体删除。
 */

import { v4 as uuidv4 } from 'uuid'

import type { BehaviorType } from '@/types'

/** 工作空间成员（mock：d-2 member 接真前的前端简化形态） */
export interface WorkspaceMember {
  id: string
  /** 实例在该空间的显示名 */
  name: string
  /** 头像 URL（缺省 fallback 到默认地鼠图） */
  avatar_url?: string | null
  /** 管家固定一个，其余都是 agent */
  role: 'supervisor' | 'agent'
  /** 来源：招毛坯模板 or 招用户已建的 Agent */
  source: 'template' | 'agent'
  /** 来源名（"研究员" / "营销文案手"），UI 标注用 */
  source_name: string
  behavior_type: BehaviorType
}

/** 每个空间固定的管家成员（supervisor）—— d-2 member 接真前通讯录 UI 用 */
export function supervisor(): WorkspaceMember {
  return {
    id: uuidv4(),
    name: '管家',
    role: 'supervisor',
    source: 'template',
    source_name: '调度',
    behavior_type: 'supervisor',
  }
}

