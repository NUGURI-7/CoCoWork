import { createContext, useContext, type ReactNode } from 'react'
import { useStore } from 'zustand'

import type { ChatState, ChatStore } from '@/stores/chat-store'

/**
 * Chat store Context —— 工厂模式下子组件拿 store 的标准通道。
 *
 * 工厂 `createChatStore({ endpoint })` 出来的 hook 不是单例，
 * 子组件（MessageList / MessageInput / blocks）通过 Context 共享，
 * 避免 prop drilling。
 *
 * 使用：
 *   const store = useMemo(() => createChatStore({ endpoint }), [endpoint])
 *   return (
 *     <ChatProvider store={store}>
 *       <MessageList />
 *       <MessageInput />
 *     </ChatProvider>
 *   )
 *
 * 子组件：
 *   const messages = useChat((s) => s.messages)
 *   const send = useChat((s) => s.send)
 */
const ChatContext = createContext<ChatStore | null>(null)

export function ChatProvider({
  store,
  children,
}: {
  store: ChatStore
  children: ReactNode
}) {
  return <ChatContext.Provider value={store}>{children}</ChatContext.Provider>
}

/**
 * 子组件用：传 selector 取片段、跟 Zustand 原生 hook 同款 API。
 *
 * 走 zustand 的 useStore(store, selector) —— 它内部用 useSyncExternalStore 注册
 * 订阅，state 变化触发组件 re-render。直接 store(selector) 不行（vanilla store
 * 没有 React 订阅机制）。
 */
export function useChat<T>(selector: (state: ChatState) => T): T {
  const store = useContext(ChatContext)
  if (!store) {
    throw new Error('useChat 必须在 <ChatProvider> 内使用')
  }
  return useStore(store, selector)
}
