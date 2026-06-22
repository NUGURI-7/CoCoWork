/**
 * 通讯录 view-model —— 统一「合成的管家」与「后端真成员」两种来源。
 *
 * 管家不是 members 表的行（它是 workspace.supervisor），故前端合成一行固定置顶；
 * 真成员由后端 MemberOut 映射而来。两者收敛成同一个 RosterMember，喂给
 * MemberRoster / MemberStrip 渲染。
 */

import type { WorkspaceMemberOut } from '@/types'

export interface RosterMember {
  /** 管家固定 'supervisor'；真成员用 member.id（踢人按它） */
  id: string
  name: string
  avatarUrl?: string | null
  /** 管家一个，其余都是 agent 成员 */
  role: 'supervisor' | 'agent'
  /** 副标题：管家=调度，成员=成员 */
  subtitle: string
}

/** 合成的管家行 —— 固定置顶、不可踢。 */
export const SUPERVISOR_ROSTER: RosterMember = {
  id: 'supervisor',
  name: '管家',
  role: 'supervisor',
  subtitle: '调度',
}

/** 后端 MemberOut → 通讯录 view-model。 */
export function memberToRoster(m: WorkspaceMemberOut): RosterMember {
  return {
    id: m.id,
    name: m.agent.name,
    avatarUrl: m.agent.avatar_url,
    role: 'agent',
    subtitle: '成员',
  }
}
