import { useEffect, useMemo } from 'react'

import { ChatProvider, useChat } from '@/components/chat/ChatProvider'
import { MessageInput } from '@/components/chat/MessageInput'
import { MessageList } from '@/components/chat/MessageList'
import { createChatStore } from '@/stores/chat-store'
import type { Agent } from '@/types'

interface PlaygroundProps {
  agent: Agent
}

/**
 * 右栏沙盒试运行 —— 跟当前 agent 试聊几句，验证配置改动效果。
 * 消息不持久化，刷新或离开页面即清；正式对话归 workspace 模块。
 *
 * 架构：
 * - 工厂 createChatStore({ endpoint }) 出独立 store hook
 * - ChatProvider 把 store 注入 MessageList / MessageInput 子组件
 * - useMemo + endpoint deps：切 agent → store 自动重建
 * - useEffect cleanup：切 agent / unmount → 中止流释放资源
 */
export function Playground({ agent }: PlaygroundProps) {
  const endpoint = `/agents/${agent.id}/playground/stream`
  const store = useMemo(() => createChatStore({ endpoint }), [endpoint])

  useEffect(() => {
    return () => {
      store.getState().reset()
    }
  }, [store])

  return (
    <div className="bg-muted/30 flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg">
      <ChatProvider store={store}>
        <PlaygroundBody agent={agent} />
      </ChatProvider>
    </div>
  )
}

function PlaygroundBody({ agent }: { agent: Agent }) {
  const isEmpty = useChat((s) => s.messages.length === 0)

  return (
    <>
      {isEmpty ? <EmptyHint agent={agent} /> : <MessageList />}
      <MessageInput />
    </>
  )
}

function EmptyHint({ agent }: { agent: Agent }) {
  return (
    <div className="text-muted-foreground/70 flex flex-1 items-center justify-center px-4 text-center text-sm">
      改改左边配置，发条消息试试 {agent.name} 的反应
    </div>
  )
}
