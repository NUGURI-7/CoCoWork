import { useCallback, useEffect, useRef } from 'react'
import { SendHorizontal, Square } from 'lucide-react'
import { EditorContent, useEditor, useEditorState } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Mention from '@tiptap/extension-mention'

import type { ApiContentBlock } from '@/types'
import { useChat } from './ChatProvider'
import type { MentionItem } from './MentionList'
import { createMentionSuggestion } from './mention-suggestion'

interface MessageInputProps {
  /** 整体禁发（如前置配置未就绪）。编辑器 + 发送键一起禁。 */
  disabled?: boolean
  /** disabled 时占位提示（告诉用户为什么发不了 / 去哪解决）。 */
  disabledHint?: string
  /**
   * @mention 候选项。传了就启用 @mention（workspace 把成员映射进来）；
   * 不传则纯文本输入框（Playground）。传空数组也算启用、只是暂无候选。
   */
  mentionItems?: MentionItem[]
}

/**
 * 消息输入框 —— TipTap 富文本底座 + 发送/停止按钮。
 *
 * 行为：
 * - Enter 发送、Shift+Enter 换行；composition（中文输入法组字）中回车不误发
 * - isLoading 时发送键变停止键 → store.stop()
 * - 发送后清空 + 重新 focus；disabled 时整体禁发、placeholder 显示 disabledHint
 * - mentionItems 传入则启用 @mention（atomic token，id 挂在 node 上、不靠反解文本）
 *
 * 纯文本（StarterKit 关掉所有富文本节点/标记）；mention 作为可选能力叠加。
 * 不带模型选择器 —— 模型在 ConfigPanel 已选、不在输入框重复 UI。
 */
export function MessageInput({
  disabled = false,
  disabledHint,
  mentionItems,
}: MessageInputProps) {
  const isLoading = useChat((s) => s.isLoading)
  const send = useChat((s) => s.send)
  const stop = useChat((s) => s.stop)

  // TipTap 的 handleKeyDown 在 mount 时固化、闭包会 stale；用 ref 读最新值
  const sendRef = useRef<() => void>(() => {})
  const placeholderRef = useRef('发送消息…')
  // @ 候选浮层是否开着 —— 开着时回车归 suggestion（选候选），不触发发送
  const mentionActiveRef = useRef(false)
  // suggestion.items 读这个 ref，支持成员异步加载（extensions 不重建）
  const mentionItemsRef = useRef<MentionItem[]>(mentionItems ?? [])
  useEffect(() => {
    mentionItemsRef.current = mentionItems ?? []
  }, [mentionItems])

  // 启用与否在 mount 时定：workspace 传（即使空数组）→ 启用；Playground 不传 → 纯文本
  const enableMention = mentionItems !== undefined

  const editor = useEditor({
    immediatelyRender: true,
    extensions: [
      // 纯文本聊天框：关掉 StarterKit 所有富文本节点/标记，只留段落 + 文本 + undo/redo
      StarterKit.configure({
        heading: false,
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        blockquote: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
        horizontalRule: false,
      }),
      Placeholder.configure({ placeholder: () => placeholderRef.current }),
      ...(enableMention
        ? [
            Mention.configure({
              HTMLAttributes: { class: 'mention' },
              renderText: ({ node }) =>
                `@${node.attrs.label ?? node.attrs.id}`,
              suggestion: createMentionSuggestion(
                () => mentionItemsRef.current,
                (active) => {
                  mentionActiveRef.current = active
                },
              ),
            }),
          ]
        : []),
    ],
    editorProps: {
      attributes: {
        class: 'tiptap-input max-h-40 min-h-[24px] overflow-y-auto outline-none',
      },
      handleKeyDown: (_view, event) => {
        // @ 候选浮层开着时，回车归 suggestion（选中候选）、不发送。
        // editorProps.handleKeyDown 在 ProseMirror 里先于 suggestion 插件跑，
        // 所以这里要主动让路：return false 让事件继续传到 suggestion。
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
          if (mentionActiveRef.current) return false
          event.preventDefault()
          sendRef.current()
          return true
        }
        return false
      },
    },
  })

  // 订阅「是否为空」—— 发送键禁用态（TipTap 内容变化默认不重渲染组件）
  const isEmpty = useEditorState({
    editor,
    selector: ({ editor }) => editor?.isEmpty ?? true,
  })

  const handleSend = useCallback(() => {
    if (!editor) return
    const text = editor.getText().trim()
    if (!text || isLoading || disabled) return
    // 取所有 @mention token 的 id（前端送全部 = v2-ready；后端 v1 只取第一个）
    const mentionedIds: string[] = []
    editor.state.doc.descendants((node) => {
      if (node.type.name === 'mention' && typeof node.attrs.id === 'string') {
        mentionedIds.push(node.attrs.id)
      }
    })
    editor.commands.clearContent()
    editor.commands.focus()
    const content: ApiContentBlock[] = [{ type: 'text', text }]
    void send(content, enableMention ? mentionedIds : undefined)
  }, [editor, isLoading, disabled, send, enableMention])

  // 把最新 handleSend 灌进 ref，供固化的 handleKeyDown 调用
  useEffect(() => {
    sendRef.current = handleSend
  }, [handleSend])

  // disabled 切可编辑态 + 同步 placeholder 文本（disabled / loading 时换提示）
  useEffect(() => {
    if (!editor) return
    editor.setEditable(!disabled)
    placeholderRef.current = disabled
      ? (disabledHint ?? '暂不可发送')
      : isLoading
        ? 'AI 正在回答…'
        : '发送消息…'
    // placeholder 是 decoration，内容没变不会自动重算 → 派发空 transaction 强制刷新
    editor.view.dispatch(editor.state.tr)
  }, [editor, disabled, disabledHint, isLoading])

  const canSend = !isEmpty && !disabled

  return (
    <div className="shrink-0 px-4 py-4 pb-8">
      <div className="mx-auto max-w-3xl">
        <div className="border-border bg-background focus-within:border-ring flex flex-col gap-2 rounded-2xl border px-4 py-3 transition-colors">
          <EditorContent editor={editor} />

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
                disabled={!canSend}
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
