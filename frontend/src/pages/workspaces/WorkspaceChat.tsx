import { useEffect, useRef, useState } from 'react'
import { Crown, Send } from 'lucide-react'
import { v4 as uuidv4 } from 'uuid'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { WorkspaceMember } from '@/types'

interface WorkspaceChatProps {
  members: WorkspaceMember[]
}

interface WSMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  /** 仅 assistant 有：发言成员快照 */
  senderId?: string
  senderName?: string
  senderColor?: string
  isSupervisor?: boolean
  created_at: string
}

/**
 * 工作空间主对话区（spec §5.4 + §6 路由）
 *
 * v0 mock 路由：消息开头 @某成员 → 那成员答；否则 → 管家答。
 * 输入框检测光标前 `@<query>` 模式，弹候选成员（不含管家——@管家走默认路径意义不大）。
 * 消息纯内存，刷新即清。
 */
export function WorkspaceChat({ members }: WorkspaceChatProps) {
  const [messages, setMessages] = useState<WSMessage[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [mentionQuery, setMentionQuery] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const supervisor = members.find((m) => m.role === 'supervisor')
  const nonSupervisors = members.filter((m) => m.role !== 'supervisor')

  // 新消息滚到底
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, pending])

  /** 检测光标前是否处于 `@<query>` 模式（@ 后无空白） */
  function detectMention() {
    const el = textareaRef.current
    if (!el) return
    const pos = el.selectionStart ?? 0
    const before = el.value.slice(0, pos)
    const m = before.match(/@([^\s@]*)$/)
    setMentionQuery(m ? m[1] : null)
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    requestAnimationFrame(detectMention)
  }

  function insertMention(member: WorkspaceMember) {
    const el = textareaRef.current
    const pos = el?.selectionStart ?? input.length
    const before = input.slice(0, pos)
    const after = input.slice(pos)
    const replaced = before.replace(/@([^\s@]*)$/, `@${member.name} `)
    const newInput = replaced + after
    setInput(newInput)
    setMentionQuery(null)
    // 复位光标到插入末尾
    const newPos = replaced.length
    requestAnimationFrame(() => {
      if (!textareaRef.current) return
      textareaRef.current.focus()
      textareaRef.current.setSelectionRange(newPos, newPos)
    })
  }

  function send() {
    const content = input.trim()
    if (!content) return

    // 解析开头 @某成员（仅匹配非 supervisor 名字）
    let target: WorkspaceMember | undefined = supervisor
    const m = content.match(/^@(\S+)\s*(.*)$/s)
    let stripped = content
    if (m) {
      const found = nonSupervisors.find((x) => x.name === m[1])
      if (found) {
        target = found
        stripped = m[2]
      }
    }

    const now = new Date().toISOString()
    setMessages((prev) => [
      ...prev,
      { id: uuidv4(), role: 'user', content, created_at: now },
    ])
    setInput('')
    setMentionQuery(null)
    setPending(true)

    setTimeout(() => {
      if (!target) {
        setPending(false)
        return
      }
      const preview = stripped.length > 24 ? `${stripped.slice(0, 24)}…` : stripped
      const replyContent =
        target.role === 'supervisor'
          ? `（mock 调度）收到，我来安排合适的成员处理："${preview}"`
          : `（mock 回复）作为「${target.source_name}」型成员，关于"${preview}"我会这么回答……`
      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          role: 'assistant',
          content: replyContent,
          senderId: target!.id,
          senderName: target!.name,
          senderColor: target!.avatar_color,
          isSupervisor: target!.role === 'supervisor',
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

  const mentionCandidates =
    mentionQuery !== null
      ? nonSupervisors.filter((mb) =>
          mb.name.toLowerCase().includes(mentionQuery.toLowerCase()),
        )
      : []
  const showMention = mentionQuery !== null && mentionCandidates.length > 0

  return (
    <>
      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <EmptyHint />
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)
        )}
        {pending && <TypingDots />}
      </div>

      {/* 输入区（含 @mention 浮层） */}
      <div className="bg-background relative shrink-0 border-t p-3">
        {showMention && (
          <div className="bg-popover absolute right-3 bottom-full left-3 mb-1 max-h-56 overflow-y-auto rounded-lg border shadow-md">
            <div className="text-muted-foreground px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
              @ 指派给…
            </div>
            <div className="space-y-0.5 p-1">
              {mentionCandidates.map((mb) => (
                <button
                  key={mb.id}
                  type="button"
                  onClick={() => insertMention(mb)}
                  className="hover:bg-muted flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left"
                >
                  <div
                    className="flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-medium text-white"
                    style={{ backgroundColor: mb.avatar_color }}
                  >
                    {mb.name.slice(0, 1)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{mb.name}</div>
                    <div className="text-muted-foreground truncate text-[11px]">
                      {mb.source === 'template' ? '模板' : 'Agent'} · {mb.source_name}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={input}
            placeholder="输入消息…（@ 唤起成员；不 @ 走管家调度）"
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onClick={detectMention}
            onKeyUp={detectMention}
            className="max-h-40 min-h-12 resize-none pr-12 text-sm"
          />
          <Button
            size="icon"
            onClick={send}
            disabled={!input.trim() || pending}
            className="absolute right-2 bottom-2 size-7"
          >
            <Send className="size-3.5" />
          </Button>
        </div>
      </div>
    </>
  )
}

function EmptyHint() {
  return (
    <div className="text-muted-foreground/70 flex h-full items-center justify-center text-center text-sm">
      发条消息开始协作 —— 输入 @ 直接指派成员，不 @ 走管家调度
    </div>
  )
}

function MessageBubble({ msg }: { msg: WSMessage }) {
  if (msg.role === 'user') {
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
        style={{ backgroundColor: msg.senderColor ?? '#888' }}
      >
        {msg.isSupervisor ? <Crown className="size-3.5" /> : msg.senderName?.slice(0, 1)}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="text-brand text-xs font-medium">{msg.senderName}</div>
        <div className="bg-background max-w-[75%] rounded-2xl rounded-tl-sm border px-3.5 py-2 text-sm">
          {msg.content}
        </div>
      </div>
    </div>
  )
}

function TypingDots() {
  return (
    <div className="flex items-start gap-2.5">
      <div className="bg-muted-foreground/30 size-7 shrink-0 rounded-full" />
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
