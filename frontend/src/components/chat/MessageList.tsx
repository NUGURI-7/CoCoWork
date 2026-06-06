import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown } from 'lucide-react'
import { bouncy } from 'ldrs'

bouncy.register()
import type {
  ApiContentBlock,
  AssistantMessage as AssistantMessageType,
  UserMessage as UserMessageType,
} from '@/types'

import { TextBlock } from './blocks/TextBlock'
import { ThinkingBlock } from './blocks/ThinkingBlock'
import { ToolUseBlock } from './blocks/ToolUseBlock'
import { useChat } from './ChatProvider'
import { MarkdownRender } from './MarkdownRender'

/** 触底容差 —— 离底部多少 px 内算"在底"。 */
const NEAR_BOTTOM_THRESHOLD = 20

/** user 消息 content（ApiContentBlock[]）→ 拼成 string 给 MarkdownRender。 */
function apiContentToText(content: ApiContentBlock[]): string {
  return content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('')
}

/**
 * 消息列表 + 智能滚动。
 *
 * 滚动策略：
 * - ResizeObserver 监听内容高度变化 → 在跟随态时滚到底
 * - 用户 wheel / touchmove 时若不在底部 → 停跟随
 * - 触底 20px 容差内 → 恢复跟随
 * - 不跟随时显示 sticky "回到最新" 按钮
 */
export function MessageList() {
  const messages = useChat((s) => s.messages)

  const scrollRef = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({
      top: el.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    })
  }, [])

  // 跟随：内容高度变化时滚到底
  useEffect(() => {
    const inner = innerRef.current
    if (!inner) return
    const ro = new ResizeObserver(() => {
      if (autoScroll) scrollToBottom()
    })
    ro.observe(inner)
    return () => ro.disconnect()
  }, [autoScroll, scrollToBottom])

  // 新消息（user push 时）强制接管 + 初次挂载滚到底
  useEffect(() => {
    setAutoScroll(true)
    scrollToBottom()
    // 仅当 messages.length 变化时触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length])

  // 用户手势 → 不在底部就停跟随
  const handleUserIntent = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const isAtBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_THRESHOLD
    if (!isAtBottom) setAutoScroll(false)
  }, [])

  // 滚动接近底部 → 恢复跟随
  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const isNearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_THRESHOLD
    if (isNearBottom) setAutoScroll(true)
  }, [])

  const resumeAutoScroll = useCallback(() => {
    setAutoScroll(true)
    scrollToBottom(true)
  }, [scrollToBottom])

  return (
    <div
      ref={scrollRef}
      className="relative flex-1 overflow-y-auto px-4 pt-6"
      onWheel={handleUserIntent}
      onTouchMove={handleUserIntent}
      onScroll={handleScroll}
    >
      <div ref={innerRef} className="mx-auto max-w-3xl space-y-6 pb-4">
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <UserMessageRow key={msg.id} message={msg} />
          ) : (
            <AssistantMessageRow key={msg.id} message={msg} />
          ),
        )}
      </div>

      {!autoScroll && (
        <div className="pointer-events-none sticky bottom-2 flex w-full justify-center">
          <button
            type="button"
            onClick={resumeAutoScroll}
            className="border-border bg-background text-muted-foreground hover:text-foreground pointer-events-auto flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border shadow-md transition-colors"
            title="回到最新"
          >
            <ArrowDown size={16} />
          </button>
        </div>
      )}
    </div>
  )
}

function UserMessageRow({ message }: { message: UserMessageType }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="bg-muted text-foreground max-w-[80%] rounded-2xl px-4 py-2.5">
        <MarkdownRender content={apiContentToText(message.content)} isUser />
      </div>
    </div>
  )
}

function AssistantMessageRow({ message }: { message: AssistantMessageType }) {
  const isStreaming = message.status === 'streaming'

  return (
    <div className="flex flex-col gap-2">
      {message.blocks.map((block) => {
        if (block.type === 'text') {
          return <TextBlock key={block.index} block={block} />
        }
        if (block.type === 'thinking') {
          return <ThinkingBlock key={block.index} block={block} />
        }
        return <ToolUseBlock key={block.index} block={block} />
      })}

      {message.status === 'error' && message.errorMessage && (
        <p className="text-destructive text-sm">{message.errorMessage}</p>
      )}

      {/* 流式中底部 loader —— l-bouncy 三球弹跳 brand 墨绿 + warning 暖橙 drop-shadow
          做"冷暖混色"光晕（ldrs 单 color 限制，混色靠外层 CSS filter）。
          完成后不显示 —— actions row 未来挂上方时配静态 logo。 */}
      {isStreaming && (
        <div
          className="mt-2 inline-block"
          style={{
            filter: 'drop-shadow(0 0 5px rgba(217, 119, 6, 0.55))',
          }}
        >
          <l-bouncy size="28" speed="1.2" color="#2f6b53" />
        </div>
      )}
    </div>
  )
}

