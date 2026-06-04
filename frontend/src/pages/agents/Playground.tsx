import { useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { Agent, Message } from '@/types'

interface PlaygroundProps {
  agent: Agent
}

/**
 * 右栏沙盒试运行：跟当前 agent 试聊几句，验证配置改动效果。
 * 消息不持久化，刷新或离开页面即清——正式对话归 workspace 模块。
 */
export function Playground({ agent }: PlaygroundProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新消息到达时滚动到底
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  function send() {
    const content = input.trim()
    if (!content) return
    if (!agent.config.model_id) {
      toast.warning('请先选择模型')
      return
    }
    const now = new Date().toISOString()
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content, created_at: now },
    ])
    setInput('')
    setPending(true)

    // 模拟 500ms 后 mock 回复
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `（mock 回复）这是来自当前模型的占位回复，等切片接 LLM。`,
          created_at: new Date().toISOString(),
        },
      ])
      setPending(false)
    }, 500)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="bg-muted/30 flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg">
      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <EmptyHint agent={agent} />
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} msg={msg} agent={agent} />)
        )}
        {pending && <TypingDots agent={agent} />}
      </div>

      {/* 输入区 */}
      <div className="bg-background shrink-0 border-t p-3">
        <div className="relative">
          <Textarea
            value={input}
            placeholder={
              agent.config.model_id
                ? `跟 ${agent.name} 试聊几句…（Enter 发送，Shift+Enter 换行）`
                : '先选择模型，然后开始试运行'
            }
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="max-h-40 min-h-12 resize-none pr-12 text-sm"
          />
          <Button
            size="icon"
            onClick={send}
            disabled={!input.trim() || pending}
            className="absolute bottom-2 right-2 size-7"
          >
            <Send className="size-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

function EmptyHint({ agent }: { agent: Agent }) {
  return (
    <div className="text-muted-foreground/70 flex h-full items-center justify-center text-sm">
      改改左边配置，发条消息试试 {agent.name} 的反应
    </div>
  )
}

function MessageBubble({ msg, agent }: { msg: Message; agent: Agent }) {
  const isUser = msg.role === 'user'
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="bg-background max-w-[75%] rounded-2xl rounded-br-sm border px-3.5 py-2 text-sm">
          {msg.content}
        </div>
      </div>
    )
  }
  return (
    <div className="flex items-start gap-2.5">
      <div
        className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
        style={{ backgroundColor: agent.config.avatar_color ?? '#2f6b53' }}
      >
        {agent.name.slice(0, 1)}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="text-brand text-xs font-medium">{agent.name}</div>
        <div className="bg-background max-w-[75%] rounded-2xl rounded-tl-sm border px-3.5 py-2 text-sm">
          {msg.content}
        </div>
      </div>
    </div>
  )
}

function TypingDots({ agent }: { agent: Agent }) {
  return (
    <div className="flex items-start gap-2.5">
      <div
        className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
        style={{ backgroundColor: agent.config.avatar_color ?? '#2f6b53' }}
      >
        {agent.name.slice(0, 1)}
      </div>
      <div className="bg-background flex gap-1 rounded-2xl rounded-tl-sm border px-3.5 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={cn('bg-muted-foreground/50 size-1.5 animate-bounce rounded-full')}
            style={{ animationDelay: `${i * 120}ms` }}
          />
        ))}
      </div>
    </div>
  )
}
