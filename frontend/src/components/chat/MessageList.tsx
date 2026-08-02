import { Fragment, memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Archive, ArrowDown, User } from 'lucide-react'
import { bouncy } from 'ldrs'

bouncy.register()
import type {
  ApiArtifactRefBlock,
  ApiContentBlock,
  ApiTextBlock,
  Artifact,
  AskAnswer,
  AssistantMessage as AssistantMessageType,
  UserMessage as UserMessageType,
} from '@/types'
import { cn } from '@/lib/utils'

import { ArtifactCard } from './ArtifactCard'
import { AttachmentChip } from './AttachmentChip'
import { AskBlock } from './blocks/AskBlock'
import { DelegateBlock } from './blocks/DelegateBlock'
import { TextBlock } from './blocks/TextBlock'
import { ThinkingBlock } from './blocks/ThinkingBlock'
import { ToolUseBlock } from './blocks/ToolUseBlock'
import { useChat } from './ChatProvider'
import { useSubagentInfo } from './SubagentDirectory'
import { MarkdownRender } from './MarkdownRender'
import { MessageActions, copyAction } from './MessageActions'
import { TokenUsageBadge } from './TokenUsageBadge'

/** assistant 消息 → 只取可见正文（text blocks）拼成纯文本，供复制。 */
function assistantBlocksToText(blocks: AssistantMessageType['blocks']): string {
  return blocks
    .filter((b) => b.type === 'text')
    .map((b) => ('content' in b ? b.content : ''))
    .join('')
}

/**
 * 「已整理此前的对话记录」分隔线。
 *
 * 画在被归档那段历史的**下方边界**上，读作「以上内容已被压成摘要」。
 * 用户往上翻会发现模型对更早的内容记得模糊，这条线告诉他分界在哪 ——
 * ChatGPT / Claude 的 compact 也是这个形态。
 *
 * 只在本次会话可见，刷新后消失（产品决策：别的项目刷新后也不留）。
 */
function CompactDivider() {
  return (
    <div className="my-2 flex items-center gap-3 px-1" role="separator">
      <span className="bg-border h-px flex-1" />
      <span className="text-muted-foreground flex items-center gap-1.5 text-xs">
        <Archive size={12} />
        已整理此前的对话记录
      </span>
      <span className="bg-border h-px flex-1" />
    </div>
  )
}

/** 触底容差 —— 离底部多少 px 内算"在底"。 */
const NEAR_BOTTOM_THRESHOLD = 20

/** user 消息 content（ApiContentBlock[]）→ 拼成 string 给 MarkdownRender。 */
function apiContentToText(content: ApiContentBlock[]): string {
  return content
    .filter((b): b is ApiTextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('')
}

/**
 * user 消息里附上的产物（后端决策 25）→ 卡片要的形状。
 *
 * 实时回显与刷新回放走的是同一个函数：前者的块是发送时本地拼的，后者的块是
 * 从 DB 读回来的（展示字段已被服务端以库为准回填）。形状一致，所以只有一条渲染路径。
 */
function attachmentsOf(content: ApiContentBlock[]): Artifact[] {
  return content
    .filter((b): b is ApiArtifactRefBlock => b.type === 'artifact_ref')
    .map((b) => ({
      id: b.artifact_id,
      filename: b.filename,
      size: b.size,
      content_type: b.content_type,
    }))
}

/**
 * 消息列表 + 智能滚动。
 *
 * 滚动策略：
 * - ResizeObserver 监听内容高度变化 → 在跟随态时滚到底
 * - 用户 wheel / touchmove 时若不在底部 → 停跟随
 * - 触底 20px 容差内 → 恢复跟随
 * - 不跟随时显示 sticky "回到最新" 按钮
 *
 * topFade：顶部渐变遮罩 —— 无边框浮层顶栏（沉浸态）下，消息滚到顶时淡出消失（Claude 风），
 * 替代硬分隔线。背景是图也不穿帮（真 alpha mask，非纯色覆盖）。
 */
export function MessageList({ topFade = false }: { topFade?: boolean }) {
  const messages = useChat((s) => s.messages)
  const isCompacting = useChat((s) => s.isCompacting)
  const compactedBeforeIds = useChat((s) => s.compactedBeforeIds)
  // 数组转 Set：渲染里每条消息都要查一次，别在 map 里做 O(n) includes
  const compactedBefore = useMemo(() => new Set(compactedBeforeIds), [compactedBeforeIds])

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
      className={cn(
        'relative flex-1 overflow-y-auto px-4',
        topFade
          ? 'pt-4 [mask-image:linear-gradient(to_bottom,transparent,#000_2rem)] [-webkit-mask-image:linear-gradient(to_bottom,transparent,#000_2rem)]'
          : 'pt-6',
      )}
      onWheel={handleUserIntent}
      onTouchMove={handleUserIntent}
      onScroll={handleScroll}
    >
      <div ref={innerRef} className="mx-auto max-w-3xl space-y-6 px-4 pb-36">
        {messages.map((msg) => (
          <Fragment key={msg.id}>
            {compactedBefore.has(msg.id) && <CompactDivider />}
            {msg.role === 'user' ? (
              <UserMessageRow message={msg} />
            ) : (
              <AssistantMessageRow message={msg} />
            )}
          </Fragment>
        ))}

        {/* 压缩中 —— 这几秒还没有 assistant 气泡（compact 两帧在 message_start
            之前到），提示只能挂在列表底部。不说「正在思考」是因为它此刻确实
            没在想问题，在归档旧记录，说清楚用户才知道等的是什么 */}
        {isCompacting && (
          <div className="text-muted-foreground flex items-center gap-2 px-1 py-2 text-sm">
            <l-bouncy size="20" speed="1.2" color="#2f6b53" />
            正在整理对话记录…
          </div>
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

// memo：流式时每个 token 都重渲染 MessageList，靠 message 引用比对跳过没变的
// 消息（immer 对未变消息保留同引用），只让正在长的那条重渲染。
const UserMessageRow = memo(function UserMessageRow({
  message,
}: {
  message: UserMessageType
}) {
  const text = apiContentToText(message.content)
  const attachments = attachmentsOf(message.content)

  return (
    <div className="group flex flex-col items-end gap-1">
      {/* 附件排在气泡上方 —— 与输入框里待发时的位置一致，发送前后不跳 */}
      {attachments.length > 0 && (
        <div className="flex max-w-[80%] flex-wrap justify-end gap-1.5">
          {attachments.map((a) => (
            <AttachmentChip key={a.id} artifact={a} />
          ))}
        </div>
      )}

      {/* 只拖了文件、没打字时不画空气泡 */}
      {text && (
        <div className="bg-muted text-foreground max-w-[80%] rounded-2xl px-4 py-2.5">
          <MarkdownRender content={text} isUser />
        </div>
      )}

      {text && <MessageActions actions={[copyAction(() => text)]} align="right" />}
    </div>
  )
})

const AssistantMessageRow = memo(function AssistantMessageRow({
  message,
}: {
  message: AssistantMessageType
}) {
  const isStreaming = message.status === 'streaming'
  // 提交人工确认的答案 —— 块本身不认识 store，由这里传下去
  const answerAsk = useChat((s) => s.answerAsk)
  const onAnswer = useCallback(
    (blockIndex: number, answer: AskAnswer) =>
      void answerAsk(message.id, blockIndex, answer),
    [answerAsk, message.id],
  )
  // 只有 @直连成员才露身份（头像 + 名）；supervisor / Playground（senderMemberId 空）
  // 保持裸气泡（ChatGPT 风、默认对话方）。
  const identity = useSubagentInfo(
    message.senderMemberId
      ? `member_${message.senderMemberId.slice(0, 8)}`
      : '',
  )

  const body = (
    <>
      {message.blocks.map((block) => {
        if (block.type === 'text') {
          return <TextBlock key={block.index} block={block} />
        }
        if (block.type === 'thinking') {
          return <ThinkingBlock key={block.index} block={block} />
        }
        if (block.type === 'delegate') {
          return <DelegateBlock key={block.index} block={block} />
        }
        if (block.type === 'ask') {
          return (
            <AskBlock key={block.index} block={block} onAnswer={onAnswer} />
          )
        }
        return <ToolUseBlock key={block.index} block={block} />
      })}

      {/* 沙箱产物 —— 这一轮交付出来的文件，排在正文之后、错误之前 */}
      {message.artifacts && message.artifacts.length > 0 && (
        <div className="mt-2 flex flex-col gap-2">
          {message.artifacts.map((a) => (
            <ArtifactCard key={a.id} artifact={a} />
          ))}
        </div>
      )}

      {message.status === 'error' && message.errorMessage && (
        <p className="text-destructive text-sm">{message.errorMessage}</p>
      )}

      {/* 流式中底部 loader —— l-bouncy 三球弹跳 brand 墨绿 + warning 暖橙 drop-shadow
          做"冷暖混色"光晕（ldrs 单 color 限制，混色靠外层 CSS filter）。 */}
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
    </>
  )

  const actions = !isStreaming && (
    <MessageActions
      actions={[copyAction(() => assistantBlocksToText(message.blocks))]}
      align="left"
      extra={
        message.tokenUsage && (
          <TokenUsageBadge usage={message.tokenUsage} blocks={message.blocks} />
        )
      }
    />
  )

  // 没有身份信息（如 Playground 沙盒）→ 裸渲染，ChatGPT 风
  if (!identity) {
    return (
      <div className="group flex flex-col gap-2">
        {body}
        {actions}
      </div>
    )
  }

  // 群聊风：左侧头像 gutter + 发送者名 + 内容（user 仍是右气泡）
  return (
    <div className="flex gap-3">
      <span className="border-border bg-background mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border">
        {identity.avatarUrl ? (
          <img
            src={identity.avatarUrl}
            alt=""
            className="h-full w-full object-cover"
          />
        ) : (
          <User size={16} />
        )}
      </span>
      <div className="group flex min-w-0 flex-1 flex-col gap-1.5">
        <span className="text-foreground text-sm font-medium">
          {identity.name}
        </span>
        <div className="flex flex-col gap-2">{body}</div>
        {actions}
      </div>
    </div>
  )
})

