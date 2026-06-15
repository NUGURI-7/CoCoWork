/**
 * Workspace API — 对接 backend/app/api/routes/workspace/*
 *
 * 路径前缀 `/workspaces`，加上 axios baseURL `/api/v1`。
 * Conversation / Message 走 nested 路径（归属校验靠后端 JOIN 一次过）。
 * 对话流（/stream）不在本文件 —— SSE 走 api/chat-stream.ts 的 streamChat，
 * endpoint 由调用方拼好注入。
 */

import { del, get, post, put } from '@/request'
import type {
  Conversation,
  ConversationCreatePayload,
  ConversationUpdatePayload,
  MemberRecruitPayload,
  Workspace,
  WorkspaceCreatePayload,
  WorkspaceMemberOut,
  WorkspaceMessage,
  WorkspaceUpdatePayload,
} from '@/types'

/** 列出当前用户的 workspace。 */
export function listWorkspaces() {
  return get<Workspace[]>('/workspaces')
}

/** 获取单个 workspace 详情。 */
export function getWorkspace(id: string) {
  return get<Workspace>(`/workspaces/${id}`)
}

/** 创建 workspace（supervisor / config 由后端给默认值）。走 silent 由表单层 toast。 */
export function createWorkspace(payload: WorkspaceCreatePayload) {
  return post<Workspace>('/workspaces', payload, { silent: true })
}

/** 更新 workspace（PUT，字段全可选）。走 silent 由表单层 toast。 */
export function updateWorkspace(id: string, payload: WorkspaceUpdatePayload) {
  return put<Workspace>(`/workspaces/${id}`, payload, { silent: true })
}

/** 删除 workspace（FK CASCADE 连带删成员 / 对话 / 消息）。 */
export function deleteWorkspace(id: string) {
  return del<null>(`/workspaces/${id}`)
}

// ============ Conversation（nested: /workspaces/{wid}/conversations） ============

/** 列出 workspace 下的对话（后端按 updated_at 倒序，最近活跃在前）。 */
export function listConversations(workspaceId: string) {
  return get<Conversation[]>(`/workspaces/${workspaceId}/conversations`)
}

/** 获取单个对话详情。 */
export function getConversation(workspaceId: string, conversationId: string) {
  return get<Conversation>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
  )
}

/** 创建对话（title 可不传，留空等系统按首轮内容自动生成）。 */
export function createConversation(
  workspaceId: string,
  payload: ConversationCreatePayload = {},
) {
  return post<Conversation>(
    `/workspaces/${workspaceId}/conversations`,
    payload,
    { silent: true },
  )
}

/** 更新对话（改标题 / 对话级 config 覆盖）。 */
export function updateConversation(
  workspaceId: string,
  conversationId: string,
  payload: ConversationUpdatePayload,
) {
  return put<Conversation>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
    payload,
    { silent: true },
  )
}

/** 删除对话（FK CASCADE 连带删消息）。 */
export function deleteConversation(workspaceId: string, conversationId: string) {
  return del<null>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
  )
}

// ============ Message（只读：写消息走对话流端点落库） ============

/** 拉对话消息历史（升序，老→新；进对话时一次性拉全量）。 */
export function listMessages(workspaceId: string, conversationId: string) {
  return get<WorkspaceMessage[]>(
    `/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
  )
}

/** 拼对话流 SSE endpoint（喂给 chat-store 的 streamChat，路径相对 axios baseURL）。 */
export function conversationStreamEndpoint(
  workspaceId: string,
  conversationId: string,
): string {
  return `/workspaces/${workspaceId}/conversations/${conversationId}/stream`
}

// ============ Member（nested: /workspaces/{wid}/members） ============

/** 列出 workspace 成员（后端按招募时间正序，先来的在前）。 */
export function listMembers(workspaceId: string) {
  return get<WorkspaceMemberOut[]>(`/workspaces/${workspaceId}/members`)
}

/** 招募一个现成 agent 进 workspace（unique 撞库后端返 409）。 */
export function recruitMember(
  workspaceId: string,
  payload: MemberRecruitPayload,
) {
  return post<WorkspaceMemberOut>(`/workspaces/${workspaceId}/members`, payload)
}

/** 踢人（移除成员，保历史消息）。 */
export function removeMember(workspaceId: string, memberId: string) {
  return del<null>(`/workspaces/${workspaceId}/members/${memberId}`)
}
