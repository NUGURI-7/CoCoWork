import { useCallback, useEffect, useRef, useState } from 'react'
import { SendHorizontal, Square } from 'lucide-react'
import { EditorContent, useEditor, useEditorState } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Mention from '@tiptap/extension-mention'
import { toast } from 'sonner'

import { cn } from '@/lib/utils'
import type { ApiContentBlock, Artifact } from '@/types'
import { AttachmentChip } from './AttachmentChip'
import {
  hasArtifactDrag,
  readArtifactDragData,
} from './artifact-drag'
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
  /**
   * 能不能把产出物面板的卡片拖进来当附件（后端决策 25）。
   * Playground 不传 —— 它的消息不入库、没有「本对话」，后端那条路直接拒（决策 26）。
   */
  attachable?: boolean
}

/** 一条消息最多附几个 —— 与后端 _MAX_ATTACHMENTS 对齐，超了在这儿就拦住 */
const MAX_ATTACHMENTS = 5

/** 从桌面拖进来的真文件。浏览器把它们放在 `Files` 这个固定类型名下。 */
function hasOsFiles(dt: DataTransfer | null): boolean {
  return !!dt && dt.types.includes('Files')
}

/**
 * 桌面文件拖进来时的说法 —— 让「不支持」和「坏了」区分开。
 *
 * 不给说法的话用户看到的是**什么都没发生**：ProseMirror 会去拿 text/plain 与
 * text/html 拼内容，而 Finder 拖出来的文件这两样都没有，于是它插了个空。
 * 本地文件上传是另一刀（届时这里换成真正的上传分支，管道不用重铺）。
 */
function rejectOsFiles(): void {
  toast('暂不支持从本地拖文件进来', {
    description: '目前只能拖右侧「产出物」面板里的文件；本地文件上传还没做。',
  })
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
  attachable = false,
}: MessageInputProps) {
  const isLoading = useChat((s) => s.isLoading)
  const send = useChat((s) => s.send)
  const stop = useChat((s) => s.stop)

  // 待发附件：拖进来先在这儿排队，点发送才随消息一起走
  const [pending, setPending] = useState<Artifact[]>([])
  // 拖到框上方时的高亮 —— 没有它用户不知道「这儿能放」
  const [dragOver, setDragOver] = useState(false)

  const addPending = useCallback((artifact: Artifact) => {
    setPending((prev) => {
      // 同一个拖两次是误操作（后端也会去重，这里拦住是为了别让用户看见两张卡）
      if (prev.some((a) => a.id === artifact.id)) return prev
      if (prev.length >= MAX_ATTACHMENTS) return prev
      return [...prev, artifact]
    })
  }, [])

  // TipTap 的 handleKeyDown / handleDrop 在 mount 时固化、闭包会 stale；用 ref 读最新值
  const sendRef = useRef<() => void>(() => {})
  const addPendingRef = useRef(addPending)
  useEffect(() => {
    addPendingRef.current = addPending
  }, [addPending])
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
  // 同理，editorProps 在 mount 时固化，这个值在闭包里读的就是当时那份。
  // attachable 由父组件写死（workspace 传、Playground 不传），运行中不会翻
  const attachableAtMount = attachable

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
      // 落在编辑器**正文区**的拖放归 ProseMirror 先看见 —— 不在这儿接住，
      // 它会按自己的规则处理（多半是当外部内容插进文档里）。
      // return true = 「我处理了」，ProseMirror 就不再插任何东西。
      // 框的其余部分（padding / 附件行）由外层 div 的 onDrop 接，两条路都通向
      // 同一个 addPending，重复也无妨（按 id 去重）。
      handleDrop: (_view, event) => {
        const dt = (event as DragEvent).dataTransfer
        if (!dt) return false
        const artifact = readArtifactDragData(dt)
        if (artifact) {
          event.preventDefault()
          addPendingRef.current(artifact)
          return true
        }
        // 桌面文件：这一刀不收，但也别让 ProseMirror 拿它去拼内容
        if (attachableAtMount && hasOsFiles(dt)) {
          event.preventDefault()
          rejectOsFiles()
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
    // 只拖了文件、一个字没打也算数 —— 「这个你看看」是合法的一句话
    if ((!text && pending.length === 0) || isLoading || disabled) return
    // 取所有 @mention token 的 id（前端送全部 = v2-ready；后端 v1 只取第一个）
    const mentionedIds: string[] = []
    editor.state.doc.descendants((node) => {
      if (node.type.name === 'mention' && typeof node.attrs.id === 'string') {
        mentionedIds.push(node.attrs.id)
      }
    })
    editor.commands.clearContent()
    editor.commands.focus()

    // 附件块排在正文之后：读的人先看见「说了什么」，再看见「给了什么」。
    // 展示字段一并送出只为本地乐观回显立刻能画卡片，后端会拿库里的覆盖
    const content: ApiContentBlock[] = [
      ...(text ? [{ type: 'text' as const, text }] : []),
      ...pending.map((a) => ({
        type: 'artifact_ref' as const,
        artifact_id: a.id,
        filename: a.filename,
        size: a.size,
        content_type: a.content_type,
      })),
    ]
    setPending([])
    void send(content, enableMention ? mentionedIds : undefined)
  }, [editor, isLoading, disabled, send, enableMention, pending])

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

  const canSend = (!isEmpty || pending.length > 0) && !disabled

  return (
    <div className="shrink-0 px-4 py-4 pb-8">
      <div className="mx-auto max-w-3xl">
        <div
          onDragOver={(e) => {
            if (!attachable || disabled) return
            // **必须 preventDefault，否则 drop 根本不会触发** ——
            // HTML5 拖放 API 最有名的那个坑：默认行为是「这里不许放」
            if (hasArtifactDrag(e.dataTransfer)) {
              e.preventDefault()
              e.dataTransfer.dropEffect = 'copy'
              setDragOver(true)
              return
            }
            // 桌面文件同样要拦：不拦的话浏览器的默认行为是**打开这个文件**，
            // 整个页面直接导航走 —— 比「没反应」糟得多。拦下来才有机会给提示
            if (hasOsFiles(e.dataTransfer)) {
              e.preventDefault()
              e.dataTransfer.dropEffect = 'copy'
            }
          }}
          onDragLeave={(e) => {
            // 只认真正离开整块的那次：拖过子元素时也会冒泡 dragleave，
            // 不判断的话高亮会一路闪
            if (e.currentTarget.contains(e.relatedTarget as Node | null)) return
            setDragOver(false)
          }}
          onDrop={(e) => {
            if (!attachable || disabled) return
            const artifact = readArtifactDragData(e.dataTransfer)
            if (artifact) {
              e.preventDefault()
              setDragOver(false)
              addPending(artifact)
              return
            }
            if (hasOsFiles(e.dataTransfer)) {
              e.preventDefault()
              setDragOver(false)
              rejectOsFiles()
            }
          }}
          className={cn(
            'border-border bg-background focus-within:border-ring flex flex-col gap-2',
            'rounded-2xl border px-4 py-3 transition-colors',
            dragOver && 'border-brand-border bg-brand-subtle',
          )}
        >
          {pending.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {pending.map((a) => (
                <AttachmentChip
                  key={a.id}
                  artifact={a}
                  onRemove={() =>
                    setPending((prev) => prev.filter((p) => p.id !== a.id))
                  }
                />
              ))}
            </div>
          )}

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
