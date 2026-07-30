/**
 * 通用对话流式消费层 —— Playground / Workspace 共用。
 *
 * 不走 axios（axios 不支持 ReadableStream），直接用 fetch + Web Streams API。
 * 鉴权 / baseURL 跟 request/index.ts 同步(localStorage token + /api/v1 vite proxy)。
 *
 * 职责拆两层：
 * 1. parseSSEStream(response)            — async generator，按 SSE 协议解析 response.body
 * 2. streamChat(endpoint, body, opts?)   — 主入口，包 fetch / auth / HTTP 错误 / signal
 *
 * 错误处理分层：
 * - 网络层（fetch 抛 / signal abort）  — let it throw，调用方 try/catch + 看 err.name
 * - 业务错误（后端 ResponseModel 壳）   — 解析后抛 ChatStreamHttpError。注意后端统一
 *   用 HTTP 200 + body.code 表达业务错误，故判据是 Content-Type 而非 response.ok
 * - SSE 流中错误（event: error 帧）     — 不在此层处理，由 store switch 接住
 */

import type { ChatStreamRequest } from '@/types'

const API_BASE = '/api/v1'

/** 一条已分行解析的 SSE 事件。 */
export interface SSEEvent {
  event: string
  data: string
}

/**
 * 业务层错误 —— prepare_stream raise(chat 模型未配 / 模板不在册等) 翻 ResponseModel 时抛出。
 *
 * 携带后端 ResponseModel 的 code + message，store 层可 instanceof 判定 / 取 code 分类处理。
 */
export class ChatStreamHttpError extends Error {
  status: number
  /** 后端 ResponseModel.code（业务错误码），非 ResponseModel 形态时为 null */
  code: number | null

  constructor(status: number, message: string, code: number | null) {
    super(message)
    this.name = 'ChatStreamHttpError'
    this.status = status
    this.code = code
  }
}

/**
 * 按 SSE 协议解析 fetch response.body —— async generator yield 出每个事件。
 *
 * SSE 协议：每个事件由 `event: <name>\ndata: <json>\n\n` 组成，事件间空行分隔。
 * 内部维护 buffer，按 `\n\n` 切分；最后一段可能不完整，留在 buffer 等下一帧。
 *
 * generator 终止(break / 抛错 / abort) 时 finally 释放 reader lock。
 */
export async function* parseSSEStream(
  response: Response,
): AsyncGenerator<SSEEvent> {
  if (!response.body) {
    throw new Error('Response body is null — SSE 流无法读取')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 按双换行切分事件块
      const parts = buffer.split('\n\n')
      // 最后一段可能未完整，留在 buffer 等下一帧
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        if (!part.trim()) continue // 过滤空块（心跳 / 空行 noise）

        let event = ''
        let data = ''
        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            event = line.slice('event: '.length)
          } else if (line.startsWith('data: ')) {
            data = line.slice('data: '.length)
          }
        }

        if (event) yield { event, data }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * 调通用对话流接口 —— SSE async generator。
 *
 * @param endpoint  完整 endpoint 路径(相对 /api/v1)，如 `/agents/${id}/playground/stream`
 * @param body      ChatStreamRequest 请求体
 * @param opts.signal  AbortController.signal —— 「停止生成」按钮 / 组件 unmount 中断
 *
 * @example
 * const ctrl = new AbortController()
 * try {
 *   for await (const { event, data } of streamChat(
 *     `/agents/${agentId}/playground/stream`,
 *     { content, history },
 *     { signal: ctrl.signal },
 *   )) {
 *     // store 按 event 分发
 *   }
 * } catch (err) {
 *   if (err instanceof ChatStreamHttpError) { ... }        // 400 配置错等
 *   else if ((err as Error).name === 'AbortError') { ... } // 用户中断
 *   else { ... }                                           // 网络异常
 * }
 */
export async function* streamChat(
  endpoint: string,
  body: ChatStreamRequest,
  opts?: { signal?: AbortSignal },
): AsyncGenerator<SSEEvent> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: opts?.signal,
  })

  // 后端统一 HTTP 200 + body.code 表达业务错误（core/exceptions/handlers.py 四个
  // handler 全是 HTTP_200_OK），所以 response.ok 对错误响应同样是 true。axios 那侧
  // 靠拦截器读 body.code 兜住，SSE 走裸 fetch 没有这层 —— 只能靠 Content-Type 分辨：
  // 正常流是 text/event-stream，出错是 application/json。漏掉这一判断的后果是
  // 错误响应被当 SSE 解析、解出零个事件、调用方 for await 空转结束，界面毫无反应。
  const isEventStream = (response.headers.get('content-type') ?? '')
    .includes('text/event-stream')
  if (!response.ok || !isEventStream) {
    // 后端 raise(ValidationException 等) → ResponseModel 壳（HTTP 200 / 4xx 皆可能）
    // 尝试解 JSON 拿 code + message，非 JSON 响应(503 nginx html 等) fallback statusText
    let code: number | null = null
    let message = response.statusText
    try {
      const data = await response.json()
      if (typeof data?.code === 'number') code = data.code
      if (typeof data?.message === 'string') message = data.message
    } catch {
      // 非 JSON 响应保留 statusText
    }
    throw new ChatStreamHttpError(response.status, message, code)
  }

  yield* parseSSEStream(response)
}
