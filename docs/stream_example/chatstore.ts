// import { defineStore } from 'pinia'
// import { computed, ref } from 'vue'
// import { streamChat } from '@/api/chat'
// import type {
//   AssistantMessage,
//   TextBlock,
//   ToolUseBlock,
//   RenderBlock,
//   MessageDeltaPayload,
//   MessageStartPayload,
//   ContentBlockDeltaPayload,
//   ContentBlockStartPayload,
//   ContentBlockStopPayload,
//   SSEErrorPayload,
//   ChatMessage,
//   ContentBlock,
//   ApiToolUseBlock,
//   ToolUseStartPayload,
//   ToolUseStopPayload,
//   ToolUseDeltaPayload,
//   ToolResultPayload,
//   ImageEventPayload,
//   ImageBlock,
//   ApiImageBlock,
// } from '@/types/chat'
//
// import {
//   listConversations as apiListConversations,
//   getConversationDetail,
//   deleteConversation as apiDeleteConversation,
//   type ConversationSummary,
// } from '@/api/chat'
//
// import { v4 as uuidv4 } from 'uuid'
//
// export const useChatStore = defineStore('chat', () => {
//   // 当前对话的消息列表（user + assistant 交替）
//   const messages = ref<ChatMessage[]>([])
//
//   // 当前正在流式输出的 assistant message
//   const streaming = ref<AssistantMessage | null>(null)
//
//   // 是否正在等待回复
//   const isLoading = ref(false)
//
//   // 对话列表（侧栏用）
//   const conversations = ref<ConversationSummary[]>([])
//
//   // 当前选中的对话 uuid
//   const currentConversationUuid = ref<string | null>(null)
//
//   // 加载对话详情时的 loading
//   const isLoadingConversation = ref(false)
//
//   /**
//    * 发送消息并消费 SSE 事件流。
//    */
//   async function sendMessage(params: {
//     message_uuid: string
//     content: string
//     provider: string
//     model: string
//   }) {
//     // 确保有 currentConversationUuid（首次进入时为 null，临时生成一个）
//     if (!currentConversationUuid) newConversation()
//
//     const conversationUuid = currentConversationUuid.value!
//
//     // 记录这次是否是"新对话"——用于发送完成后决定是否刷新侧栏
//     const isNewConversation = !conversations.value.some((c: any) => c.uuid === conversationUuid)
//
//     const userMessageUuid = uuidv4()
//
//     // 先把 user message 加到列表里（乐观渲染）
//     messages.value.push({ role: 'user', uuid: userMessageUuid, content: params.content })
//     isLoading.value = true
//
//     // 送给后端的 content 是 block 数组（为 P3 多模态预留位置）
//     const contentBlocks: ContentBlock[] = [{ type: 'text', text: params.content }]
//
//     try {
//       // 消费异步迭代器
//       for await (const { event, data } of streamChat({
//         conversation_uuid: conversationUuid,
//         message_uuid: params.message_uuid,
//         content: contentBlocks,
//         provider: params.provider,
//         model: params.model,
//       })) {
//         const payload = JSON.parse(data)
//
//         switch (event) {
//           case 'message_start': {
//             const d = payload as MessageStartPayload
//             const msg: AssistantMessage = {
//               role: 'assistant',
//               uuid: d.message_uuid,
//               model: d.model,
//               provider: d.provider,
//               status: 'streaming',
//               blocks: [],
//               usage: null,
//               stopReason: null,
//               errorMessage: null,
//             }
//             streaming.value = msg
//             messages.value.push(msg)
//             break
//           }
//
//           case 'content_block_start': {
//             const d = payload as ContentBlockStartPayload
//             if (d.type === 'text' && streaming.value) {
//               const block: TextBlock = {
//                 type: 'text',
//                 index: d.index,
//                 status: 'active',
//                 content: '',
//               }
//               streaming.value.blocks.push(block)
//             }
//             break
//           }
//
//           case 'content_block_delta': {
//             const d = payload as ContentBlockDeltaPayload
//             if (streaming.value) {
//               const block = streaming.value.blocks.find((b) => b.index === d.index)
//               if (block && block.type === 'text') {
//                 block.content += d.text
//               }
//             }
//             break
//           }
//
//           case 'content_block_stop': {
//             const d = payload as ContentBlockStopPayload
//             if (streaming.value) {
//               const block = streaming.value.blocks.find((b) => b.index === d.index)
//               if (block && block.type === 'text') {
//                 block.status = 'done'
//               }
//             }
//             break
//           }
//
//           case 'tool_use_start': {
//             const d = payload as ToolUseStartPayload
//             if (streaming.value) {
//               const block: ToolUseBlock = {
//                 type: 'tool_use',
//                 index: d.index,
//                 status: 'building',
//                 id: d.id,
//                 name: d.name,
//                 inputPreview: d.input_preview,
//                 partialInputJson: '',
//                 resultSummary: null,
//                 resultData: null,
//                 collapsed: false,
//               }
//               streaming.value.blocks.push(block)
//             }
//             break
//           }
//
//           case 'tool_use_delta': {
//             const d = payload as ToolUseDeltaPayload
//             if (streaming.value) {
//               const block = streaming.value.blocks.find((b) => b.index === d.index)
//               if (block && block.type === 'tool_use') {
//                 block.partialInputJson += d.partial_json
//               }
//             }
//             break
//           }
//
//           case 'tool_use_stop': {
//             const d = payload as ToolUseStopPayload
//             if (streaming.value) {
//               const block = streaming.value.blocks.find((b) => b.index === d.index)
//               if (block && block.type === 'tool_use') {
//                 block.status = 'calling'
//                 // 尝试把累积的 JSON 解析成 inputPreview（失败就保持原样）
//                 try {
//                   const parsed = JSON.parse(block.partialInputJson)
//                   // 常见情况：参数是 {"query": "..."}，取第一个字符串值作为 preview
//                   const firstValue = Object.values(parsed).find((v) => typeof v === 'string')
//                   if (typeof firstValue === 'string') {
//                     block.inputPreview = firstValue
//                   }
//                 } catch {
//                   // partial_json 不完整或格式异常，保留后端给的 preview
//                 }
//               }
//             }
//             break
//           }
//
//           case 'tool_result': {
//             const d = payload as ToolResultPayload
//             if (streaming.value) {
//               const block = streaming.value.blocks.find((b) => b.index === d.index)
//               if (block && block.type === 'tool_use') {
//                 block.status = d.status
//                 block.resultSummary = d.result_summary
//                 block.resultData = d.result_data
//               }
//             }
//             break
//           }
//
//           case 'message_delta': {
//             const d = payload as MessageDeltaPayload
//             if (streaming.value) {
//               streaming.value.usage = d.usage
//               streaming.value.stopReason = d.stop_reason
//             }
//             break
//           }
//
//           case 'image': {
//             const d = payload as ImageEventPayload
//             if (!streaming.value) break
//             // 移除占位（loading 没被认领的兜底）
//             if (d.status === 'removed') {
//               streaming.value.blocks = streaming.value.blocks.filter(
//                 (b) => !(b.type === 'image' && b.id === d.id),
//               )
//               break
//             }
//
//             const existing = streaming.value.blocks.find(
//               (b) => b.type === 'image' && b.id === d.id,
//             ) as ImageBlock | undefined
//
//             if (!existing) {
//               // 首次收到该 id（通常是 loading 状态）→ 创建 block
//               const block: ImageBlock = {
//                 type: 'image',
//                 index: streaming.value.blocks.length,
//                 id: d.id,
//                 status: d.status,
//                 url: d.url ?? null,
//                 errorMessage: d.message ?? null,
//               }
//               streaming.value.blocks.push(block)
//             } else {
//               // 后续 ready / error 事件 → 更新既有 block
//               existing.status = d.status
//               if (d.url) existing.url = d.url
//               if (d.message) existing.errorMessage = d.message
//             }
//             break
//           }
//
//           case 'message_stop': {
//             if (streaming.value) {
//               // 兜底：把所有还处于 'active' 的 text block 收尾，避免最后一段文字没收到
//               // content_block_stop（例如工具轮之后直接走 AgentRunResultEvent 的情况）导致光标继续闪
//               for (const block of streaming.value.blocks) {
//                 if (block.type === 'text' && block.status === 'active') {
//                   block.status = 'done'
//                 }
//               }
//               streaming.value.status = 'completed'
//               streaming.value = null
//             }
//             break
//           }
//
//           case 'error': {
//             const d = payload as SSEErrorPayload
//             if (streaming.value) {
//               streaming.value.status = 'error'
//               streaming.value.errorMessage = d.message
//               streaming.value = null
//             }
//             break
//           }
//         }
//       }
//     } catch (e: any) {
//       // 网络错误（fetch 本身失败）
//       if (streaming.value) {
//         streaming.value.status = 'error'
//         streaming.value.errorMessage = e.message || 'connect error'
//         streaming.value = null
//       }
//     } finally {
//       isLoading.value = false
//
//       // 首次对话：流结束后(已入库)刷新侧栏，让新对话出现在列表里
//       if (isNewConversation) {
//         loadConversations().catch(() => {
//           // 刷新失败不影响主流程，静默处理
//         })
//       }
//     }
//   }
//
//   /**
//    * 拉取当前用户的对话列表，填充侧栏。
//    */
//   async function loadConversations() {
//     const res = await apiListConversations()
//     conversations.value = res.data as ConversationSummary[]
//   }
//
//   /**
//    * 加载指定对话的完整历史（含消息），切换为当前对话。
//    */
//   async function loadConversation(uuid: string) {
//     isLoadingConversation.value = true
//     try {
//       const res = await getConversationDetail(uuid)
//       const detail = res.data
//
//       currentConversationUuid.value = uuid
//
//       // 后端扁平 messages → 前端渲染结构
//       messages.value = detail.messages.map((msg: any): ChatMessage => {
//         // DB 里的 content 已经是 ContentBlock[] 了
//         const blocks = (msg.content ?? []) as ContentBlock[]
//         if (msg.role === 'user') {
//           // user 目前只会是 text block，拼成一个字符串给渲染层
//           const text = blocks
//             // type predicate：过滤 text block 并将数组类型从 ContentBlock[] 收窄为 TextBlock[]
//             .filter((b): b is Extract<ContentBlock, { type: 'text' }> => b.type === 'text')
//             .map((b) => b.text)
//             .join('')
//
//           return {
//             role: 'user',
//             uuid: msg.uuid,
//             content: text,
//           }
//         }
//
//         // assistant：把 DB 的 ContentBlock[] 映射成 RenderBlock[]
//         const renderBlocks: RenderBlock[] = blocks.map((b, i) => {
//           if (b.type === 'text') {
//             return {
//               type: 'text',
//               index: i,
//               status: 'done',
//               content: b.text,
//             }
//           }
//           if (b.type === 'image') {
//             const apiBlock = b as ApiImageBlock
//             return {
//               type: 'image',
//               index: i,
//               id: apiBlock.id,
//               status: 'ready',
//               url: apiBlock.url,
//               errorMessage: null,
//             }
//           }
//           // tool_use
//           const apiBlock = b as ApiToolUseBlock
//           const firstValue = Object.values(apiBlock.input).find((v) => typeof v === 'string')
//           return {
//             type: 'tool_use',
//             index: i,
//             status: apiBlock.status,
//             id: apiBlock.id,
//             name: apiBlock.name,
//             inputPreview:
//               typeof firstValue === 'string' ? firstValue : JSON.stringify(apiBlock.input),
//             partialInputJson: JSON.stringify(apiBlock.input),
//             resultSummary:
//               typeof apiBlock.output === 'string'
//                 ? apiBlock.output
//                 : JSON.stringify(apiBlock.output).slice(0, 200),
//             resultData: apiBlock.output,
//             collapsed: true,
//           }
//         })
//
//         return {
//           role: 'assistant',
//           uuid: msg.uuid,
//           model: detail.model,
//           provider: detail.provider,
//           status: 'completed',
//           blocks: renderBlocks,
//           usage: null,
//           stopReason: null,
//           errorMessage: null,
//         }
//       })
//
//       streaming.value = null
//     } finally {
//       isLoadingConversation.value = false
//     }
//   }
//
//   /**
//    * 开始一个新对话：清空消息，生成新的 uuid。
//    * 注意：此时 uuid 还没在后端存在，要等第一次 sendMessage 触发后端 get_or_create 才会落库。
//    */
//   function newConversation() {
//     messages.value = []
//     streaming.value = null
//     currentConversationUuid.value = uuidv4()
//   }
//
//   /**
//    * 删除一条对话。如果删的是当前对话，自动切到新对话状态。
//    */
//   async function removeConversation(uuid: string) {
//     await apiDeleteConversation(uuid)
//
//     conversations.value = conversations.value.filter((c: any) => c.uuid !== uuid)
//
//     if (currentConversationUuid.value === uuid) {
//       newConversation()
//     }
//   }
//
//   const lastAssistantUuid = computed(() => {
//     for (let i = messages.value.length - 1; i >= 0; i--) {
//       if (messages.value[i]?.role === 'assistant') {
//         return messages.value[i]?.uuid
//       }
//     }
//     return null
//   })
//
//   return {
//     messages,
//     streaming,
//     isLoading,
//     conversations,
//     currentConversationUuid,
//     isLoadingConversation,
//     lastAssistantUuid,
//     loadConversation,
//     newConversation,
//     removeConversation,
//     loadConversations,
//     sendMessage,
//   }
// })
