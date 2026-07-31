/**
 * DB 历史消息 → chat 渲染层形态的翻译器（workspace 侧）。
 *
 * 与后端分层对称：后端「桶（runtime 通用）+ 翻译（workspace route）」，
 * 前端「chat-store（通用）+ 本文件（workspace 专属翻译）」——
 * chat 层不知道 WorkspaceMessage 的存在。
 *
 * 块形态同构：DB content = SSE 事件攒平（snake_case），还原 RenderBlock
 * 的字段映射与流式 dispatch 同款，UI 状态字段按「已完成」补默认值。
 */

import { previewFromPartialJson } from '@/stores/chat-store'
import type {
  ApiContentBlock,
  ChatMessage,
  DelegateBlock,
  RenderBlock,
  WorkspaceMessage,
} from '@/types'

/** 单个 DB 块 → RenderBlock（text / thinking / tool_use）；index 由调用方分配。 */
function translateOne(
  b: Record<string, unknown>,
  index: number,
): RenderBlock | null {
  if (b.type === 'text' && typeof b.text === 'string') {
    return { type: 'text', index, status: 'done', content: b.text }
  }

  if (b.type === 'thinking' && typeof b.thinking === 'string') {
    return {
      type: 'thinking',
      index,
      status: 'done',
      content: b.thinking,
      collapsed: true,
    }
  }

  if (b.type === 'tool_use') {
    const partialJson =
      typeof b.partial_json === 'string' ? b.partial_json : ''
    return {
      type: 'tool_use',
      index,
      // DB status: success / error 原样；null = 没等到结局（流被掐），
      // 翻 calling —— 静态灰色正常展示（名字 / 参数可看，无结果区）
      status:
        b.status === 'success'
          ? 'success'
          : b.status === 'error'
            ? 'error'
            : 'calling',
      id: typeof b.id === 'string' ? b.id : '',
      name: typeof b.name === 'string' ? b.name : '',
      // DB 落库的 input_preview 是空串，用流式同款解析从参数 JSON 补
      inputPreview: previewFromPartialJson(partialJson) ?? '',
      partialInputJson: partialJson,
      resultSummary:
        typeof b.result_summary === 'string' ? b.result_summary : null,
      resultData: b.result_data ?? null,
      collapsed: true,
    }
  }

  // 未知块类型静默跳过 —— 协议演化后老前端不炸
  return null
}

/**
 * DB 扁平块（带 subagent 戳）→ RenderBlock[]，重建 DelegateBlock 嵌套。
 *
 * 与实时 dispatch 对称：name='task' 的 tool_use 块 → DelegateBlock（从 partial_json
 * 解析 subagent_type + description）；带 subagent 戳的块 → 归最近一个同成员的派活块。
 * index 全局重编（主流 + 嵌套共用一条递增序列，保证 React key 唯一）。
 */
function toRenderBlocks(content: Record<string, unknown>[]): RenderBlock[] {
  const root: RenderBlock[] = []
  let idx = 0

  // 新数据：按 delegate_id ↔ callId 精确匹配（同名成员并发也分得清）
  const findByCallId = (callId: string): DelegateBlock | undefined => {
    for (let i = root.length - 1; i >= 0; i--) {
      const b = root[i]
      if (b.type === 'delegate' && b.callId === callId) return b
    }
    return undefined
  }
  // 老数据（无 delegate_id 戳）：回退到成员名匹配 —— 单派活能正确还原，
  // 同名并发的老消息保持既有行为（不因本次改动更糟）
  const findByName = (subagent: string): DelegateBlock | undefined => {
    for (let i = root.length - 1; i >= 0; i--) {
      const b = root[i]
      if (b.type === 'delegate' && b.subagentName === subagent) return b
    }
    return undefined
  }

  for (const b of content) {
    const subagent = typeof b.subagent === 'string' ? b.subagent : undefined

    // task 工具块 → 重建派活块（subagent 为空 = 管家主流的派活动作）
    if (b.type === 'tool_use' && b.name === 'task' && !subagent) {
      const argsJson =
        typeof b.partial_json === 'string' ? b.partial_json : ''
      let subagentName = ''
      let task = ''
      try {
        const args = JSON.parse(argsJson) as {
          subagent_type?: string
          description?: string
        }
        if (typeof args.subagent_type === 'string')
          subagentName = args.subagent_type
        if (typeof args.description === 'string') task = args.description
      } catch {
        // args 不完整 —— 派活块降级，归属不到的子块会落主流
      }
      root.push({
        type: 'delegate',
        index: idx++,
        callId: typeof b.id === 'string' ? b.id : '',
        status: b.status === 'error' ? 'error' : 'done',
        subagentName,
        task,
        blocks: [],
        collapsed: true,
        argsJson,
      })
      continue
    }

    const rb = translateOne(b, idx++)
    if (!rb) continue
    // 归属：新数据用 delegate_id→callId 精确匹配；老数据回退成员名；都没有则落主流
    const delegateId =
      typeof b.delegate_id === 'string' ? b.delegate_id : undefined
    const delegate = delegateId
      ? findByCallId(delegateId)
      : subagent
        ? findByName(subagent)
        : undefined
    const target = delegate?.blocks ?? root
    target.push(rb)
  }

  return root
}

/** DB user 消息 content → ApiContentBlock[]（只认 text 块，形态同构直接收窄）。 */
function toApiContent(content: Record<string, unknown>[]): ApiContentBlock[] {
  return content
    .filter(
      (b): b is { type: 'text'; text: string } =>
        b.type === 'text' && typeof b.text === 'string',
    )
    .map((b) => ({ type: 'text', text: b.text }))
}

/**
 * DB 历史 → chat-store 可 hydrate 的 ChatMessage[]。
 *
 * status 映射：done / stopped → completed（半截消息安静躺着，ChatGPT 同款）、
 * error → error + 错误条文案。
 */
export function workspaceMessagesToChatMessages(
  messages: WorkspaceMessage[],
): ChatMessage[] {
  return messages.map((m): ChatMessage => {
    if (m.role === 'user') {
      return { role: 'user', id: m.id, content: toApiContent(m.content) }
    }
    return {
      role: 'assistant',
      id: m.id,
      status: m.status === 'error' ? 'error' : 'completed',
      blocks: toRenderBlocks(m.content),
      usage: null,
      // 本轮消耗：流式那份由 message_stop 帧写进同名字段，这里是刷新后从 DB 还原的
      // 同一份数字（后端 usage_summary 一处产出，SSE 与落库同源）
      tokenUsage: {
        prompt_tokens: m.prompt_tokens,
        completion_tokens: m.completion_tokens,
        token_usage: m.token_usage,
      },
      stopReason: null,
      errorMessage:
        m.status === 'error' ? m.error_message || '生成失败' : null,
      // 产物卡片：流式那份由 artifacts 事件写进同名字段，这里是刷新后从 DB 还原的同一份
      artifacts: m.artifacts,
      // @直连成员答的消息：从 DB 身份字段译出成员 id（supervisor 应答为 undefined）
      senderMemberId:
        m.sender_kind === 'member' && m.sender_member_id
          ? m.sender_member_id
          : undefined,
    }
  })
}
