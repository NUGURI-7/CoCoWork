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
import { toast } from 'sonner'
import { v4 as uuidv4 } from 'uuid'

import { ChatStreamHttpError, streamChat } from '@/api/chat-stream'
import type {
  ApiContentBlock,
  ApiHistoryMessage,
  ArtifactsPayload,
  CompactStopPayload,
  AssistantMessage,
  ChatMessage,
  ContentBlockDeltaPayload,
  ContentBlockStartPayload,
  ContentBlockStopPayload,
  DelegateBlock,
  ErrorPayload,
  MessageDeltaPayload,
  MessageStopPayload,
  MessageStartPayload,
  RenderBlock,
  TextBlock,
  ToolResultPayload,
  ToolUseBlock,
  ToolUseDeltaPayload,
  ToolUseStartPayload,
  ToolUseStopPayload,
} from '@/types'

// ============ 内部 helpers ============

/** 前端生成的消息临时 id（user 消息 / 错误兜底消息用） */
function uuid(): string {
  return uuidv4()
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
 * 导出共用：历史还原（DB 落库的 input_preview 是空串）同款解析。
 */
export function previewFromPartialJson(partial: string): string | null {
  try {
    const obj = JSON.parse(partial)
    const v = Object.values(obj).find((x) => typeof x === 'string')
    return typeof v === 'string' ? v : null
  } catch {
    return null
  }
}

/**
 * 事件落点容器 —— 带 delegate_id 戳的块进对应派活块（DelegateBlock）内部 blocks，
 * 否则进主流 blocks。
 *
 * 按 callId 精确匹配（delegate_id 是 task 的 tool_call_id，全局唯一）：同名成员被
 * 并发派活时，两张卡片的 callId 不同，据此把各自的子块分得清清楚楚 —— 不再靠
 * 「成员名 + running」去猜（那会把两路都塞进最后一张卡，导致文字串卡）。
 */
function containerFor(
  blocks: RenderBlock[],
  delegateId: string | undefined,
): RenderBlock[] {
  if (delegateId) {
    for (let i = blocks.length - 1; i >= 0; i--) {
      const b = blocks[i]
      if (b.type === 'delegate' && b.callId === delegateId) {
        return b.blocks
      }
    }
  }
  return blocks
}

// ============ State / Actions 类型 ============

export interface ChatState {
  messages: ChatMessage[]
  isLoading: boolean
  /**
   * 产物变更计数 —— 每来一帧 artifacts 事件 +1。
   *
   * 它是**信号不是数据**：产物本体已经挂在消息上（`ChatMessage.artifacts`），
   * 这个计数只用来告诉对话之外的东西（产出物面板）「该重拉一次了」。
   * 于是面板的数据来源始终只有接口一处，不存在两份状态要对齐。
   */
  artifactsRevision: number

  /**
   * 正在压缩历史 —— compact_start 到 compact_stop 之间为 true。
   *
   * 这两帧在 message_start **之前**到（后端压缩发生在装配之前），所以此刻还没有
   * assistant 气泡，提示只能挂在列表底部。用户在这几秒里是干等的，必须给反馈。
   */
  isCompacting: boolean
  /**
   * 该在哪些消息**之前**画「已整理此前的对话记录」分隔线。
   *
   * 存的是压缩发生那一刻最后一条消息的 id（= 本轮刚发出的那条 user 消息），
   * 分隔线画在它上方，读作「以上内容已归档」。用数组而不是单值：一次会话里
   * 可能压多次，每次留一道。
   *
   * **刻意只活在内存里**：刷新后消失（产品决策，别的项目也不留痕）。
   */
  compactedBeforeIds: string[]

  send: (content: ApiContentBlock[], mentionedMemberIds?: string[]) => Promise<void>
  stop: () => void
  reset: () => void
  /** 用 DB 历史一次性灌入 messages（进对话回放）。流中不可调 —— 调用方靠
   *  「历史加载完成前禁发」保证时序，store 不做条件合并。 */
  hydrate: (messages: ChatMessage[]) => void
}

/**
 * Vanilla store API（不是 React hook） —— Zustand 工厂 + Context 标准 pattern：
 * 工厂返 vanilla store、Provider 传它、子组件用 `useStore(store, selector)` 订阅。
 */
export type ChatStore = StoreApi<ChatState>

// ============ 工厂 ============

export function createChatStore({
  endpoint,
  sendHistory = true,
}: {
  endpoint: string
  /** body 是否携带 history。沙盒（Playground）前端持历史须送 true；
   *  workspace 历史真源在 DB、后端自己拼，传 false 不送。 */
  sendHistory?: boolean
}): ChatStore {
  // AbortController 内部维护 —— send 时新建、stop / reset / 完成时丢弃
  let abortCtrl: AbortController | null = null
  // 这一轮被 @ 的成员 id —— send 时记下，message_start 盖到 assistant 上（乐观显示成员身份）
  let pendingSenderMemberId: string | undefined

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
                tokenUsage: null,
                stopReason: null,
                errorMessage: null,
                senderMemberId: pendingSenderMemberId,
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
              containerFor(m.blocks, p.delegate_id).push(block)
            })
            return
          }
          case 'content_block_delta': {
            const p = payload as ContentBlockDeltaPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = containerFor(m.blocks, p.delegate_id).find(
                (x) => x.index === p.index,
              )
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
              const b = containerFor(m.blocks, p.delegate_id).find(
                (x) => x.index === p.index,
              )
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
              // task 工具 = 管家派活 → 建派活块（占位主流，内部装子 agent 的块）
              if (p.name === 'task' && !p.subagent) {
                const delegate: DelegateBlock = {
                  type: 'delegate',
                  index: p.index,
                  callId: p.id,
                  status: 'running',
                  subagentName: '',
                  task: '',
                  blocks: [],
                  collapsed: false,
                  argsJson: '',
                }
                m.blocks.push(delegate)
                return
              }
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
              containerFor(m.blocks, p.delegate_id).push(block)
            })
            return
          }
          case 'tool_use_delta': {
            const p = payload as ToolUseDeltaPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = containerFor(m.blocks, p.delegate_id).find(
                (x) => x.index === p.index,
              )
              if (b?.type === 'delegate') b.argsJson += p.partial_json
              else if (b?.type === 'tool_use')
                b.partialInputJson += p.partial_json
            })
            return
          }
          case 'tool_use_stop': {
            const p = payload as ToolUseStopPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = containerFor(m.blocks, p.delegate_id).find(
                (x) => x.index === p.index,
              )
              if (b?.type === 'delegate') {
                // task args 收齐 → 解析派给谁（subagent_type）+ 派的活（description）
                try {
                  const args = JSON.parse(b.argsJson) as {
                    subagent_type?: string
                    description?: string
                  }
                  if (typeof args.subagent_type === 'string')
                    b.subagentName = args.subagent_type
                  if (typeof args.description === 'string')
                    b.task = args.description
                } catch {
                  // args 不完整 —— 派活块降级，不崩
                }
              } else if (b?.type === 'tool_use') {
                b.status = 'calling'
                const preview = previewFromPartialJson(b.partialInputJson)
                if (preview !== null) b.inputPreview = preview
              }
            })
            return
          }
          case 'tool_result': {
            const p = payload as ToolResultPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = containerFor(m.blocks, p.delegate_id).find(
                (x) => x.index === p.index,
              )
              if (b?.type === 'delegate') {
                b.status = p.status === 'error' ? 'error' : 'done'
              } else if (b?.type === 'tool_use') {
                b.status = p.status
                b.resultSummary = p.result_summary
                b.resultData = p.result_data
              }
            })
            return
          }
          case 'message_delta': {
            const p = payload as MessageDeltaPayload
            // 子 agent 自己一轮结束的 usage —— 不更新主消息。
            // 判据用 delegate_id 而非 subagent：前者是 adapter 按泳道盖的戳（后端
            // 分账用的也是它），后者靠模型元数据推，不如前者硬。
            if (p.delegate_id) return
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              m.usage = p.usage
              m.stopReason = p.stop_reason
            })
            return
          }
          case 'compact_start': {
            // 历史超线，后端停下来先把旧的压成摘要。这一帧之后要等几秒才有正文
            set((s) => {
              s.isCompacting = true
            })
            return
          }
          case 'compact_stop': {
            const p = payload as CompactStopPayload
            set((s) => {
              s.isCompacting = false
              // ok=false 是「摘要没生成出来、这轮降级用全量历史」——不是错误，
              // 这一轮照常出结果，所以不弹错也不画线：确实什么都没归档
              if (!p.ok) return
              const last = s.messages[s.messages.length - 1]
              if (last) s.compactedBeforeIds.push(last.id)
            })
            return
          }
          case 'artifacts': {
            const p = payload as ArtifactsPayload
            // 后端保证这一帧在 message_stop 之前到，所以挂得上当前这条消息
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              m.artifacts = p.artifacts
              // 计数 +1 = 对话之外的消费者（产出物面板）该重拉了
              s.artifactsRevision += 1
            })
            return
          }
          case 'message_stop': {
            const p = payload as MessageStopPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              // 本轮消耗汇总：后端算好一次性捎在终止帧里（前端不自己累加，
              // 免得跟落库那份算出两个数）。汇总失败时整组字段缺席 → 留 null。
              if (p.prompt_tokens !== undefined) {
                m.tokenUsage = {
                  prompt_tokens: p.prompt_tokens,
                  completion_tokens: p.completion_tokens ?? 0,
                  token_usage: p.token_usage ?? [],
                }
              }
              // 兜底：把所有还 active 的 text / thinking block 收尾（含派活块内部），
              // 防止后端漏发 content_block_stop 导致光标一直闪
              const sweep = (blocks: RenderBlock[]) => {
                for (const b of blocks) {
                  if (
                    (b.type === 'text' || b.type === 'thinking') &&
                    b.status === 'active'
                  ) {
                    b.status = 'done'
                    if (b.type === 'thinking') b.collapsed = true
                  } else if (b.type === 'delegate') {
                    sweep(b.blocks)
                    if (b.status === 'running') b.status = 'done'
                  }
                }
              }
              sweep(m.blocks)
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

        // 完整现场留 Console —— 「链路都在、界面却没反应」这类问题看 UI 看不出断点
        console.error('[chat-store] stream failed:', err)

        // HTTP 层错误（模型不存在 / 模板不在册等配置问题）额外弹 Toast：
        // SSE 不走 axios，request/index.ts 拦截器那套 toast 兜不到它。且这轮
        // 后端压根没落 assistant 消息，只挂消息级错误条的话刷新一次痕迹全无。
        if (isHttp) toast.error(msg)

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
              tokenUsage: null,
              stopReason: null,
              errorMessage: msg,
            })
          }
        })
      }

      return {
        messages: [],
        isLoading: false,
        artifactsRevision: 0,
        isCompacting: false,
        compactedBeforeIds: [],

        async send(content, mentionedMemberIds) {
          // 防重入 —— 上一轮还在跑时不允许新发送
          if (get().isLoading) return

          // 1) 推 user message + 计算 history（送给后端的 = 之前几轮，不含本轮）
          set((s) => {
            s.messages.push({ role: 'user', id: uuid(), content })
            s.isLoading = true
          })
          const history = sendHistory
            ? messagesToHistory(get().messages.slice(0, -1))
            : []

          // 这一轮谁应答：被 @ 的成员（v1 取第一个）；没 @ 则 supervisor（undefined）
          pendingSenderMemberId = mentionedMemberIds?.[0]

          // 2) 新建 abort signal
          abortCtrl = new AbortController()

          try {
            for await (const { event, data } of streamChat(
              endpoint,
              { content, history, mentioned_member_ids: mentionedMemberIds },
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
            s.isCompacting = false
            s.compactedBeforeIds = []
          })
        },

        hydrate(messages) {
          set((s) => {
            s.messages = messages
            s.isLoading = false
          })
        },
      }
    }),
  )
}
