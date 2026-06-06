/**
 * 通用对话 store —— Playground / Workspace 共用，工厂模式。
 *
 * 每个对话场景 mount 时调一次 createChatStore({ endpoint }) 拿一份独立 store；
 * 跨场景 / 跨实例隔离（路由切换自动重建、不串数据）。
 *
 * State：
 * - messages    完整对话（user + assistant 交替）
 * - isLoading   send 期间 true
 *
 * Actions：
 * - send(content)  发送 + 消费 SSE
 * - stop()         abort + 立即 UI 反馈
 * - reset()        清状态 + 中断
 *
 * 错误展示：消息级 —— 错误信息挂在那条出错的 AssistantMessage.errorMessage 上，
 * UI 渲染该消息时画错误条。store 不开顶层 error 字段。
 *
 * 关键设计：流中 assistant message 永远是 messages 的最后一条 —— 所有 dispatch
 * case 都通过 `s.messages[s.messages.length - 1]` 拿 Draft 引用 mutate。
 *
 * 不存独立 `streaming` 字段引用：immer 是 copy-on-write，存两个引用指向同一对象
 * 时 mutate 一边会复制对象、另一边不变 → 引用分裂 → UI 渲染永远空白。
 *
 * AbortController 内部维护，stop() 是公开接口。
 */

import { createStore, type StoreApi } from 'zustand'
import { immer } from 'zustand/middleware/immer'

import { ChatStreamHttpError, streamChat } from '@/api/chat-stream'
import type {
  ApiContentBlock,
  ApiHistoryMessage,
  AssistantMessage,
  ChatMessage,
  ContentBlockDeltaPayload,
  ContentBlockStartPayload,
  ContentBlockStopPayload,
  ErrorPayload,
  MessageDeltaPayload,
  MessageStartPayload,
  RenderBlock,
  TextBlock,
  ToolResultPayload,
  ToolUseBlock,
  ToolUseDeltaPayload,
  ToolUseStartPayload,
} from '@/types'

// ============ 内部 helpers ============

/** 前端生成的消息临时 id（user 消息 / 错误兜底消息用） */
function uuid(): string {
  return crypto.randomUUID()
}

/**
 * messages → 后端 history schema 摊平。
 *
 * - user：content 直接透传（已经是 ApiContentBlock[]）
 * - assistant：从 RenderBlock 摊平回 ApiContentBlock（P0 只取 done 的 text block；
 *   P1 加 ToolUseBlock 持久化时这里扩）
 */
function messagesToHistory(messages: ChatMessage[]): ApiHistoryMessage[] {
  return messages.map((m) => {
    if (m.role === 'user') return { role: 'user', content: m.content }
    const content: ApiContentBlock[] = m.blocks
      .filter((b): b is TextBlock => b.type === 'text' && b.status === 'done')
      .map((b) => ({ type: 'text', text: b.content }))
    return { role: 'assistant', content }
  })
}

/**
 * tool_use_stop 时解 partial_json 取首个 string 值作 inputPreview。
 * 失败保留后端 preview 原值。
 */
function previewFromPartialJson(partial: string): string | null {
  try {
    const obj = JSON.parse(partial)
    const v = Object.values(obj).find((x) => typeof x === 'string')
    return typeof v === 'string' ? v : null
  } catch {
    return null
  }
}

// ============ State / Actions 类型 ============

export interface ChatState {
  messages: ChatMessage[]
  isLoading: boolean

  send: (content: ApiContentBlock[]) => Promise<void>
  stop: () => void
  reset: () => void
}

/**
 * Vanilla store API（不是 React hook） —— Zustand 工厂 + Context 标准 pattern：
 * 工厂返 vanilla store、Provider 传它、子组件用 `useStore(store, selector)` 订阅。
 */
export type ChatStore = StoreApi<ChatState>

// ============ 工厂 ============

export function createChatStore({
  endpoint,
}: {
  endpoint: string
}): ChatStore {
  // AbortController 内部维护 —— send 时新建、stop / reset / 完成时丢弃
  let abortCtrl: AbortController | null = null

  return createStore<ChatState>()(
    immer((set, get) => {
      // ===== SSE event 分发（11 case + default warn）=====
      // 包成 closure，set/get 直接从外层闭包拿，避免传 helper 的类型签名地狱
      function dispatch(event: string, payload: unknown) {
        switch (event) {
          case 'message_start': {
            const p = payload as MessageStartPayload
            set((s) => {
              s.messages.push({
                role: 'assistant',
                id: p.id,
                status: 'streaming',
                blocks: [],
                usage: null,
                stopReason: null,
                errorMessage: null,
              })
            })
            return
          }
          case 'content_block_start': {
            const p = payload as ContentBlockStartPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const block: RenderBlock =
                p.type === 'thinking'
                  ? {
                      type: 'thinking',
                      index: p.index,
                      status: 'active',
                      content: '',
                      collapsed: false,
                    }
                  : {
                      type: 'text',
                      index: p.index,
                      status: 'active',
                      content: '',
                    }
              m.blocks.push(block)
            })
            return
          }
          case 'content_block_delta': {
            const p = payload as ContentBlockDeltaPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = m.blocks.find((x) => x.index === p.index)
              if (!b) return
              if (b.type === 'text' && p.type === 'text_delta' && p.text) {
                b.content += p.text
              } else if (
                b.type === 'thinking' &&
                p.type === 'thinking_delta' &&
                p.thinking
              ) {
                b.content += p.thinking
              }
            })
            return
          }
          case 'content_block_stop': {
            const p = payload as ContentBlockStopPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = m.blocks.find((x) => x.index === p.index)
              if (!b) return
              if (b.type === 'text' || b.type === 'thinking') {
                b.status = 'done'
                // thinking 完成默认折叠（节省视觉空间）
                if (b.type === 'thinking') b.collapsed = true
              }
            })
            return
          }
          case 'tool_use_start': {
            const p = payload as ToolUseStartPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const block: ToolUseBlock = {
                type: 'tool_use',
                index: p.index,
                status: 'building',
                id: p.id,
                name: p.name,
                inputPreview: p.input_preview,
                partialInputJson: '',
                resultSummary: null,
                resultData: null,
                collapsed: false,
              }
              m.blocks.push(block)
            })
            return
          }
          case 'tool_use_delta': {
            const p = payload as ToolUseDeltaPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = m.blocks.find((x) => x.index === p.index)
              if (b?.type === 'tool_use') b.partialInputJson += p.partial_json
            })
            return
          }
          case 'tool_use_stop': {
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = m.blocks.find(
                (x) => x.index === (payload as { index: number }).index,
              )
              if (b?.type !== 'tool_use') return
              b.status = 'calling'
              const preview = previewFromPartialJson(b.partialInputJson)
              if (preview !== null) b.inputPreview = preview
            })
            return
          }
          case 'tool_result': {
            const p = payload as ToolResultPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = m.blocks.find((x) => x.index === p.index)
              if (b?.type !== 'tool_use') return
              b.status = p.status
              b.resultSummary = p.result_summary
              b.resultData = p.result_data
            })
            return
          }
          case 'message_delta': {
            const p = payload as MessageDeltaPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              m.usage = p.usage
              m.stopReason = p.stop_reason
            })
            return
          }
          case 'message_stop': {
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              // 兜底：把所有还 active 的 text / thinking block 收尾
              // 防止后端漏发 content_block_stop 导致光标一直闪
              for (const b of m.blocks) {
                if (
                  (b.type === 'text' || b.type === 'thinking') &&
                  b.status === 'active'
                ) {
                  b.status = 'done'
                  if (b.type === 'thinking') b.collapsed = true
                }
              }
              m.status = 'completed'
            })
            return
          }
          case 'error': {
            const p = payload as ErrorPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              m.status = 'error'
              m.errorMessage = p.message
            })
            return
          }
          default: {
            // 未知事件类型 —— 协议演化时会进这里。
            // 静默忽略 + warn，比 throw 友好（兼容后端先于前端发版加新事件）
            console.warn(`[chat-store] unhandled SSE event: ${event}`)
          }
        }
      }

      // ===== 错误兜底（catch 块用）=====
      function handleStreamError(err: unknown) {
        // AbortError —— stop() 已经处理 UI 反馈，不要覆盖
        if ((err as Error)?.name === 'AbortError') return

        const isHttp = err instanceof ChatStreamHttpError
        const msg = isHttp
          ? err.message || '请求失败'
          : (err as Error)?.message || '网络错误'

        set((s) => {
          const last = s.messages[s.messages.length - 1] as
            | AssistantMessage
            | undefined
          if (last?.role === 'assistant' && last.status === 'streaming') {
            last.status = 'error'
            last.errorMessage = msg
          } else {
            // 还没收到 message_start —— 推一条假 AssistantMessage 挂错误条
            s.messages.push({
              role: 'assistant',
              id: uuid(),
              status: 'error',
              blocks: [],
              usage: null,
              stopReason: null,
              errorMessage: msg,
            })
          }
        })
      }

      return {
        messages: [],
        isLoading: false,

        async send(content) {
          // 防重入 —— 上一轮还在跑时不允许新发送
          if (get().isLoading) return

          // 1) 推 user message + 计算 history（送给后端的 = 之前几轮，不含本轮）
          set((s) => {
            s.messages.push({ role: 'user', id: uuid(), content })
            s.isLoading = true
          })
          const history = messagesToHistory(get().messages.slice(0, -1))

          // 2) 新建 abort signal
          abortCtrl = new AbortController()

          try {
            for await (const { event, data } of streamChat(
              endpoint,
              { content, history },
              { signal: abortCtrl.signal },
            )) {
              const payload = data ? JSON.parse(data) : {}
              dispatch(event, payload)
            }
          } catch (err) {
            handleStreamError(err)
          } finally {
            set((s) => {
              s.isLoading = false
            })
            abortCtrl = null
          }
        },

        stop() {
          // 立即 UI 反馈 + 真正 abort（全链路真停、见 runner / adapter cancel 设计）
          if (abortCtrl) abortCtrl.abort()
          set((s) => {
            const last = s.messages[s.messages.length - 1] as
              | AssistantMessage
              | undefined
            if (last?.role === 'assistant' && last.status === 'streaming') {
              last.status = 'error'
              last.errorMessage = '已中断生成'
            }
            s.isLoading = false
          })
        },

        reset() {
          if (abortCtrl) abortCtrl.abort()
          abortCtrl = null
          set((s) => {
            s.messages = []
            s.isLoading = false
          })
        },
      }
    }),
  )
}
