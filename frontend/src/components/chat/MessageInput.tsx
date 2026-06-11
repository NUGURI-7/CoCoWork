import { useCallback, useRef, useState, type KeyboardEvent } from 'react'
import { SendHorizontal, Square } from 'lucide-react'

import { useChat } from './ChatProvider'

interface MessageInputProps {
  /** 整体禁发（如前置配置未就绪）。textarea + 发送键一起禁。 */
  disabled?: boolean
  /** disabled 时 textarea 的占位提示（告诉用户为什么发不了 / 去哪解决）。 */
  disabledHint?: string
}

/**
 * 消息输入框 —— textarea + 发送/停止按钮。
 *
 * 行为：
 * - Enter 发送、Shift+Enter 换行
 * - composition 拦截中文输入法（防选词回车误发）
 * - textarea auto-resize（scrollHeight 同步、上限 max-h-40）
 * - isLoading 时发送键变停止键 → 调 store.stop()
 * - 发送后清空 + 重置高度 + 重新 focus
 * - disabled 时整体禁发，placeholder 显示 disabledHint（场景前置校验用，
 *   如 workspace 管家未配模型）
 *
 * 不带模型选择器 —— CoCoWork 模型在 ConfigPanel 已选、不在输入框重复 UI。
 */
export function MessageInput({ disabled = false, disabledHint }: MessageInputProps) {
  const isLoading = useChat((s) => s.isLoading)
  const send = useChat((s) => s.send)
  const stop = useChat((s) => s.stop)

  const [input, setInput] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isLoading || disabled) return
    setInput('')
    // 下一帧重置高度（state 变更 → DOM 更新后再 measure）
    requestAnimationFrame(autoResize)
    textareaRef.current?.focus()
    await send([{ type: 'text', text }])
  }, [input, isLoading, send, autoResize])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key !== 'Enter' || e.shiftKey || isComposing) return
      e.preventDefault()
      handleSend()
    },
    [isComposing, handleSend],
  )

  return (
    <div className="shrink-0 px-4 py-4 pb-8">
      <div className="mx-auto max-w-3xl">
        <div className="border-border bg-background focus-within:border-ring flex flex-col gap-2 rounded-2xl border px-4 py-3 transition-colors">
          <textarea
            ref={textareaRef}
            rows={1}
            disabled={disabled}
            placeholder={
              disabled
                ? (disabledHint ?? '暂不可发送')
                : isLoading
                  ? 'AI 正在回答…'
                  : '发送消息…'
            }
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              autoResize()
            }}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={() => setIsComposing(false)}
            onKeyDown={handleKeyDown}
            className="placeholder:text-muted-foreground max-h-40 min-h-[24px] resize-none bg-transparent outline-none"
          />

          <div className="flex items-center justify-end">
            {isLoading ? (
              <button
                type="button"
                onClick={stop}
                className="bg-foreground text-background hover:bg-foreground/90 shrink-0 cursor-pointer rounded-lg p-2 transition"
                title="停止生成"
              >
                <Square size={18} fill="currentColor" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || disabled}
                className="bg-primary text-primary-foreground hover:bg-primary/90 shrink-0 cursor-pointer rounded-lg p-2 transition disabled:cursor-not-allowed disabled:opacity-40"
                title="发送"
              >
                <SendHorizontal size={18} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
