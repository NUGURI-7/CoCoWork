// // import { del, get } from '@/request'
// // import type { Ref } from 'vue'
// // import type { ContentBlock } from '@/types/chat'
//
// interface SSEEvent {
//   event: string
//   data: string
// }
//
// /**
//  * 解析 SSE 文本流，逐个 yield 出事件。
//  */
// async function* praseSSEStream(response: Response) {
//   const reader = response.body!.getReader()
//   const decoder = new TextDecoder()
//
//   let buffer = ''
//
//   while (true) {
//     const { done, value } = await reader.read()
//     if (done) break
//
//     buffer += decoder.decode(value, { stream: true })
//
//     // 按双换行切分事件
//     const parts = buffer.split('\n\n')
//     // 最后一段可能是不完整的，留在 buffer 里
//     buffer = parts.pop()!
//
//     for (const part of parts) {
//       // 过滤空块 ，空字符串 为 false
//       if (!part.trim()) continue
//
//       let event = ''
//       let data = ''
//
//       for (const line of part.split('\n')) {
//         if (line.startsWith('event: ')) {
//           event = line.slice(7)
//         } else if (line.startsWith('data: ')) {
//           data = line.slice(6)
//         }
//       }
//
//       if (event) {
//         yield { event, data }
//       }
//     }
//   }
// }
//
// const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:7999/api/nuguri/v1'
//
// /**
//  * 发送消息并返回 SSE 事件的 async iterator。
//  */
//
// export async function* streamChat(params: {
//   conversation_uuid: string
//   message_uuid: string
//   content: ContentBlock[]
//   provider: string
//   model: string
// }): AsyncGenerator<SSEEvent> {
//   const token = localStorage.getItem('token')
//
//   const response = await fetch(`${API_BASE}/chat/send`, {
//     method: 'POST',
//     headers: {
//       'Content-Type': 'application/json',
//       Authorization: `Bearer ${token}`,
//     },
//     body: JSON.stringify(params),
//   })
//
//   if (!response.ok) {
//     throw new Error(`HTTP ${response.status}: ${response.statusText}`)
//   }
//
//   yield* praseSSEStream(response)
// }
//
// export interface ConversationSummary {
//   uuid: string
//   title: string
//   provider: string
//   model: string
//   created_at: string
//   updated_at: string
// }
//
// export interface ConversationDetail extends ConversationSummary {
//   messages: Array<{
//     uuid: string
//     role: 'user' | 'assistant' | 'system'
//     content: ContentBlock[]
//     created_at: string
//   }>
// }
//
// export const listConversations = (loading?: Ref<boolean>) =>
//   get('/chat/conversations', undefined, loading)
//
// export const getConversationDetail = (uuid: string, loading?: Ref<boolean>) =>
//   get(`/chat/conversations/${uuid}`, undefined, loading)
//
// export const deleteConversation = (uuid: string, loading?: Ref<boolean>) =>
//   del(`/chat/conversations/${uuid}`, undefined, undefined, loading)
