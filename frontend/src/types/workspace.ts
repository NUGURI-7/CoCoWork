/**
 * Workspace 模块类型 — 对齐后端 schemas/workspace/*（WorkspaceOut / ConversationOut / MessageOut）
 *
 * API 字段 snake_case 透传（项目约定，与后端零映射）。
 * UI 画图期的 mock 形态（内嵌 members/conversations）已迁往 pages/workspaces/mock.ts，
 * d-2 招募 / 成员接真时随 mock 一起退役。
 */

import type { Artifact, TokenUsageRow } from './chat'

// ============ Workspace ============

/** 对齐后端 WorkspaceOut */
export interface Workspace {
  id: string
  name: string
  description: string
  avatar_url: string
  /** 内置管家完整配置（AgentConfig 形态 jsonb），d-1 前端只透传不编辑 */
  supervisor: Record<string, unknown>
  /** workspace 自身配置（路由策略 / 开场白 / 共享资源），v1 前端暂不消费 */
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** 对齐后端 WorkspaceCreate（supervisor / config 由后端给默认值） */
export interface WorkspaceCreatePayload {
  name: string
  description?: string
  avatar_url?: string
}

/** 对齐后端 WorkspaceUpdate（PATCH 风格，字段全可选） */
export interface WorkspaceUpdatePayload {
  name?: string
  description?: string
  avatar_url?: string
  supervisor?: Record<string, unknown>
  config?: Record<string, unknown>
}

// ============ Conversation ============

/** 对齐后端 ConversationOut */
export interface Conversation {
  id: string
  workspace_id: string
  /** 空串 = 标题待生成（创建时不强求，首轮对话后系统补） */
  title: string
  /** 对话级临时覆盖（换模型 / 开 thinking），v1 前端暂不消费 */
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** 对齐后端 ConversationCreate */
export interface ConversationCreatePayload {
  title?: string
}

/** 对齐后端 ConversationUpdate */
export interface ConversationUpdatePayload {
  title?: string
  config?: Record<string, unknown>
}

/**
 * 对齐后端 ConversationTitleOut —— 只有标题，不是整条 Conversation。
 *
 * 后端刻意返窄：起名请求与对话流请求并发，返回这一刻 updated_at 等字段
 * 很可能已被流那边改过，返整条会诱使前端拿旧快照整条覆盖。
 */
export interface ConversationTitle {
  title: string
}

// ============ Message ============

/** 协议层角色（对齐后端 MessageRole） */
export type MessageRole = 'user' | 'assistant'

/** 业务层发送方：真人 / 管家 / 普通成员（对齐后端 SenderKind） */
export type SenderKind = 'user' | 'supervisor' | 'member'

/**
 * 落库状态（对齐后端 MessageStatus；流式中间态不入库）。
 *
 * interrupted **不是终态** —— 这条消息停在人工确认的表单上，还没说完，
 * 等用户填完由「继续」接口续写。
 */
export type MessageStatus = 'done' | 'error' | 'stopped' | 'interrupted'

/**
 * 对齐后端 MessageOut。
 *
 * content 块形态 = SSE 事件攒平（text / thinking / tool_use，snake_case），
 * 与流式协议同构 —— 历史还原成 RenderBlock 时复用流式同款翻译逻辑。
 * 命名带 Workspace 前缀以区分 chat.ts 的渲染层 Message union。
 */
export interface WorkspaceMessage {
  id: string
  conversation_id: string
  role: MessageRole
  sender_kind: SenderKind
  /** 发送的成员 id（踢人后置 null 保历史）；user / supervisor 消息恒为 null */
  sender_member_id: string | null
  content: Record<string, unknown>[]
  mentioned_member_ids: string[]
  status: MessageStatus
  error_message: string
  /** 这条消息产出的沙箱产物。流式那份走 SSE artifacts 帧，这里是刷新后回放用的 */
  artifacts: Artifact[]
  /** 本轮输入 token 合计（含子 agent）。流式那份走 message_stop 帧 */
  prompt_tokens: number
  /** 本轮输出 token 合计（含子 agent） */
  completion_tokens: number
  /** 消耗明细：一行一个计费单元；delegate_id 为 null 的那行是 supervisor */
  token_usage: TokenUsageRow[]
  created_at: string
  updated_at: string
}

/**
 * 对齐后端 WorkspaceArtifactItem —— 产出物面板的列表项。
 *
 * 比消息里那个 `Artifact` 多「它是哪来的」：产物绑 workspace 不绑对话，
 * 面板跨对话聚合，所以每项得说清自己出自哪个对话、哪条消息。
 */
export interface WorkspaceArtifact extends Artifact {
  conversation_id: string
  conversation_name: string
  message_id: string
  created_at: string
}

// ============ Member（招募进来的 agent 引用） ============

/** 对齐后端 MemberOut.agent —— 通讯录展示用的 agent 摘要。 */
export interface MemberAgentInfo {
  id: string
  name: string
  /** 引用的内置模板 registry key */
  template: string
  /** 头像 URL（后端从 config.ui.avatar_url 摊出，未配为 null） */
  avatar_url: string | null
}

/**
 * 对齐后端 MemberOut。
 *
 * 成员是对 agent 的不可变引用（workspace 侧无覆盖配置）；agent 内嵌摘要由后端
 * prefetch 摊出，前端无需再 N+1 拉 agent 详情。管家（supervisor）不在此列 ——
 * 它是 workspace.supervisor，不是 members 表的行。
 */
export interface WorkspaceMemberOut {
  id: string
  workspace_id: string
  agent: MemberAgentInfo
  created_at: string
  updated_at: string
}

/** 对齐后端 MemberRecruitIn —— 招募一个现成 agent。 */
export interface MemberRecruitPayload {
  agent_id: string
}
