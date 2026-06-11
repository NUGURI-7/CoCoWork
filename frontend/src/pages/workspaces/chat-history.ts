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
  RenderBlock,
  WorkspaceMessage,
} from '@/types'

/** DB 块（jsonb dict）→ RenderBlock。index 按数组下标重编（DB 不存 index）。 */
function toRenderBlocks(content: Record<string, unknown>[]): RenderBlock[] {
  const blocks: RenderBlock[] = []

  content.forEach((b, index) => {
    if (b.type === 'text' && typeof b.text === 'string') {
      blocks.push({ type: 'text', index, status: 'done', content: b.text })
      return
    }

    if (b.type === 'thinking' && typeof b.thinking === 'string') {
      blocks.push({
        type: 'thinking',
        index,
        status: 'done',
        content: b.thinking,
        collapsed: true,
      })
      return
    }

    if (b.type === 'tool_use') {
      const partialJson =
        typeof b.partial_json === 'string' ? b.partial_json : ''
      blocks.push({
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
      })
    }
    // 未知块类型静默跳过 —— 协议演化后老前端不炸
  })

  return blocks
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
      stopReason: null,
      errorMessage:
        m.status === 'error' ? m.error_message || '生成失败' : null,
    }
  })
}
