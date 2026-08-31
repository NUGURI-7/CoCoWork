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
import { isFileOpTool } from '@/components/chat/blocks/tool-format'
import type {
  ApiContentBlock,
  ApiHistoryMessage,
  ArtifactsPayload,
  AskAnswer,
  InterruptPayload,
  CompactStopPayload,
  AssistantMessage,
  ChatMessage,
  ContentBlockDeltaPayload,
  ContentBlockStartPayload,
  ContentBlockStopPayload,
  DelegateBlock,
  ErrorPayload,
  FileOp,
  FileOpsBlock,
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

/**
 * 按块编号找到那个块 —— 顶层找不到就钻进文件操作组里找它的某个 op。
 *
 * tool_use_delta / tool_use_stop / tool_result 三个事件都只带 index，而文件操作
 * 被收进了组里、不在容器顶层。组本身用组内第一个 op 的编号，所以顶层那次 find
 * 会命中组、而不是要找的那个 op —— 因此**先钻组、后认顶层**，顺序不能反。
 *
 * 返回 RenderBlock | FileOp，调用方按 'type' in b 区分（FileOp 没有 type 字段）。
 */
function findBlockByIndex(
  blocks: RenderBlock[],
  index: number,
): RenderBlock | FileOp | undefined {
  for (const b of blocks) {
    if (b.type === 'file_ops') {
      const op = b.ops.find((o) => o.index === index)
      if (op) return op
    }
  }
  return blocks.find((b) => b.index === index)
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
  /**
   * 提交人工确认的答案，从存档接着往下跑。
   *
   * 与 send 是两条独立的流，但续的是**同一条消息** —— 后端用同一个 message_id，
   * 前端也把新内容追加进同一个气泡（message_start 那里认 id 复用）。
   *
   * 没配 resumeEndpoint 的 store（Playground）调用无效果：那边不支持人工确认。
   */
  answerAsk: (messageId: string, blockIndex: number, answer: AskAnswer) => Promise<void>
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

/**
 * 文本增量攒批的窗口。
 *
 * 每个 token 单独 set 一次会把重渲染频率顶到模型的吐字速率（25~40 次/秒）。
 * 单次渲染耗时随内容增长，一旦超过 token 到达间隔就再也追不上：队列越积越长、
 * 每轮要处理的更多，正反馈直到主线程 100% 占满、页面完全不响应，只能等流结束
 * 才排空。攒 80ms 合并成一次，把频率钉死在 12 次/秒，与模型多快无关。
 */
const DELTA_FLUSH_MS = 80

interface PendingDelta {
  index: number
  delegateId: string | undefined
  kind: 'text_delta' | 'thinking_delta'
  text: string
}

// ============ 工厂 ============

export function createChatStore({
  endpoint,
  sendHistory = true,
  resumeEndpoint,
}: {
  endpoint: string
  /** body 是否携带 history。沙盒（Playground）前端持历史须送 true；
   *  workspace 历史真源在 DB、后端自己拼，传 false 不送。 */
  sendHistory?: boolean
  /** 人工确认的「继续」地址（按 messageId 拼）。不传 = 该 store 不支持人工确认
   *  —— Playground 就是这样：它的消息不入库，停下来也无处恢复。 */
  resumeEndpoint?: (messageId: string) => string
}): ChatStore {
  // AbortController 内部维护 —— send 时新建、stop / reset / 完成时丢弃
  let abortCtrl: AbortController | null = null
  // 这一轮被 @ 的成员 id —— send 时记下，message_start 盖到 assistant 上（乐观显示成员身份）
  let pendingSenderMemberId: string | undefined

  return createStore<ChatState>()(
    immer((set, get) => {
      // ===== 文本增量攒批（见 DELTA_FLUSH_MS）=====

      /** key = `${delegateId ?? ''}#${index}`，同一个块的增量按到达顺序拼接 */
      const pendingDeltas = new Map<string, PendingDelta>()
      let flushTimer: number | null = null

      /** 把攒着的增量一次性写进 store。清空缓冲 + 撤掉待触发的定时器。 */
      function flushDeltas() {
        if (flushTimer !== null) {
          clearTimeout(flushTimer)
          flushTimer = null
        }
        if (pendingDeltas.size === 0) return
        const batch = [...pendingDeltas.values()]
        pendingDeltas.clear()
        set((s) => {
          const m = s.messages[s.messages.length - 1]
          if (m?.role !== 'assistant') return
          for (const item of batch) {
            const b = containerFor(m.blocks, item.delegateId).find(
              (x) => x.index === item.index,
            )
            if (!b) continue
            if (b.type === 'text' && item.kind === 'text_delta') {
              b.content += item.text
            } else if (b.type === 'thinking' && item.kind === 'thinking_delta') {
              b.content += item.text
            }
          }
        })
      }

      function scheduleFlush() {
        if (flushTimer !== null) return
        flushTimer = window.setTimeout(() => {
          flushTimer = null
          flushDeltas()
        }, DELTA_FLUSH_MS)
      }

      /** 丢弃攒着的增量（清空时用）—— 消息都不留了，缓冲里的字没有归宿。 */
      function discardDeltas() {
        if (flushTimer !== null) {
          clearTimeout(flushTimer)
          flushTimer = null
        }
        pendingDeltas.clear()
      }

      // ===== SSE event 分发（11 case + default warn）=====
      // 包成 closure，set/get 直接从外层闭包拿，避免传 helper 的类型签名地狱
      function dispatch(event: string, payload: unknown) {
        // 文本增量不立刻落库，先攒着 —— 见 DELTA_FLUSH_MS 处的说明
        if (event === 'content_block_delta') {
          const p = payload as ContentBlockDeltaPayload
          const text =
            p.type === 'text_delta'
              ? p.text
              : p.type === 'thinking_delta'
                ? p.thinking
                : undefined
          if (!text) return
          const key = `${p.delegate_id ?? ''}#${p.index}`
          const existing = pendingDeltas.get(key)
          if (existing) {
            existing.text += text
          } else {
            pendingDeltas.set(key, {
              index: p.index,
              delegateId: p.delegate_id,
              kind: p.type,
              text,
            })
          }
          scheduleFlush()
          return
        }

        // 其余事件都可能依赖「前面的字已经写进去了」（block_stop 收尾、
        // tool_result 落状态、message_stop 结算）—— 先把攒的刷掉再处理，
        // 否则顺序会错乱：块都停了，字还在缓冲里
        flushDeltas()

        switch (event) {
          case 'message_start': {
            const p = payload as MessageStartPayload
            set((s) => {
              // 「继续」那条流也会发这一帧，但它续的是同一条消息（后端用的是同一个
              // message_id）—— 撞上就沿用原气泡、只把状态改回 streaming，
              // 不然用户填完表单会凭空多出一个空气泡
              const last = s.messages[s.messages.length - 1]
              if (last?.role === 'assistant' && last.id === p.id) {
                last.status = 'streaming'
                last.errorMessage = null
                return
              }
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
              const container = containerFor(m.blocks, p.delegate_id)

              // 文件操作不单独占块，追加进当前这一组（末尾那个 file_ops）。
              // 末尾不是 file_ops 说明中间插了别的东西 —— 那一组已经断了，开新的
              if (isFileOpTool(p.name)) {
                const op: FileOp = {
                  index: p.index,
                  status: 'building',
                  id: p.id,
                  name: p.name,
                  partialInputJson: '',
                  resultSummary: null,
                  resultData: null,
                }
                const last = container[container.length - 1]
                if (last?.type === 'file_ops') {
                  last.ops.push(op)
                  return
                }
                const group: FileOpsBlock = {
                  type: 'file_ops',
                  index: p.index,
                  ops: [op],
                  collapsed: true,
                }
                container.push(group)
                return
              }

              const block: ToolUseBlock = {
                type: 'tool_use',
                index: p.index,
                status: 'building',
                id: p.id,
                name: p.name,
                displayName: p.display_name,
                inputPreview: p.input_preview,
                partialInputJson: '',
                resultSummary: null,
                resultData: null,
                collapsed: false,
              }
              container.push(block)
            })
            return
          }
          case 'tool_use_delta': {
            const p = payload as ToolUseDeltaPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = findBlockByIndex(
                containerFor(m.blocks, p.delegate_id),
                p.index,
              )
              if (!b) return
              if (!('type' in b)) b.partialInputJson += p.partial_json
              else if (b.type === 'delegate') b.argsJson += p.partial_json
              else if (b.type === 'tool_use')
                b.partialInputJson += p.partial_json
            })
            return
          }
          case 'tool_use_stop': {
            const p = payload as ToolUseStopPayload
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              const b = findBlockByIndex(
                containerFor(m.blocks, p.delegate_id),
                p.index,
              )
              if (!b) return
              if (!('type' in b)) {
                // 文件操作：参数收齐即进入等待执行；摘要渲染时现算，不落状态
                b.status = 'calling'
              } else if (b.type === 'delegate') {
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
              const b = findBlockByIndex(
                containerFor(m.blocks, p.delegate_id),
                p.index,
              )
              if (!b) return
              if (!('type' in b)) {
                b.status = p.status
                b.resultSummary = p.result_summary
                b.resultData = p.result_data
              } else if (b.type === 'delegate') {
                b.status = p.status === 'error' ? 'error' : 'done'
              } else if (b.type === 'tool_use') {
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
          case 'interrupt': {
            const p = payload as InterruptPayload
            const ask = p.asks[0] // 后端恒发单元素：中断是一个一个来的
            if (!ask) return
            set((s) => {
              const m = s.messages[s.messages.length - 1]
              if (m?.role !== 'assistant') return
              m.blocks.push({
                type: 'ask',
                // 接在已有块之后。中断不是模型流式输出的一部分（没有自己的
                // index），自己算一个
                index: m.blocks.length
                  ? Math.max(...m.blocks.map((b) => b.index)) + 1
                  : 0,
                interruptId: ask.id,
                payload: ask.payload,
                answer: null,
                submitting: false,
              })
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
              // 「停在表单上」不是说完了 —— 气泡留着、下面渲染表单，等用户作答。
              // 后端只在中断时带这个字段，正常结束时缺席
              m.status = p.reason === 'interrupted' ? 'awaiting' : 'completed'
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
            // 流没走到 message_stop 就断了（中断 / 网络错）时，缓冲里可能还压着
            // 最后一批字 —— 补一次 flush，不然那几个字永远显示不出来
            flushDeltas()
            set((s) => {
              s.isLoading = false
            })
            abortCtrl = null
          }
        },

        async answerAsk(messageId, blockIndex, answer) {
          if (!resumeEndpoint || get().isLoading) return

          // 先把这个块标记成提交中：按钮禁用、防止连点两次
          const markSubmitting = (submitting: boolean) => {
            set((s) => {
              const m = s.messages.find(
                (x) => x.role === 'assistant' && x.id === messageId,
              )
              if (m?.role !== 'assistant') return
              const b = m.blocks.find(
                (x) => x.type === 'ask' && x.index === blockIndex,
              )
              if (b?.type === 'ask') b.submitting = submitting
            })
          }
          markSubmitting(true)
          set((s) => {
            s.isLoading = true
          })

          abortCtrl = new AbortController()
          try {
            for await (const { event, data } of streamChat(
              resumeEndpoint(messageId),
              answer,
              { signal: abortCtrl.signal },
            )) {
              dispatch(event, data ? JSON.parse(data) : {})
            }
            // 流跑完了才把答案落到块上 —— 表单随即变成只读的结果行。
            // 放在这里而不是提交前：中途失败时表单还在，用户可以重试
            set((s) => {
              const m = s.messages.find(
                (x) => x.role === 'assistant' && x.id === messageId,
              )
              if (m?.role !== 'assistant') return
              const b = m.blocks.find(
                (x) => x.type === 'ask' && x.index === blockIndex,
              )
              if (b?.type === 'ask') b.answer = answer
            })
          } catch (err) {
            handleStreamError(err)
          } finally {
            // 同 send：续跑的流也可能没走到 message_stop 就断，补一次 flush
            flushDeltas()
            markSubmitting(false)
            set((s) => {
              s.isLoading = false
            })
            abortCtrl = null
          }
        },

        stop() {
          // 立即 UI 反馈 + 真正 abort（全链路真停、见 runner / adapter cancel 设计）
          if (abortCtrl) abortCtrl.abort()
          // 缓冲里压着的是「已经生成出来的字」—— 中断只停后续生成，不该把
          // 这不到 80ms 的内容吞掉；先落库再标中断态，顺序才对
          flushDeltas()
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
          discardDeltas()
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
