import { useEffect, useRef, useState } from 'react'
import dayjs from 'dayjs'
import { Check, Pencil, Trash2 } from 'lucide-react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { cn } from '@/lib/utils'
import {
  useStreamStatusStore,
  type ConversationStatus,
} from '@/stores/stream-status'
import { useConversationTitle } from '@/stores/workspace-session'
import type { Conversation } from '@/types'

/** 对话状态点：running 墨绿脉冲 / error 红；idle 不画（保持清爽）。 */
export function StatusDot({ status }: { status: ConversationStatus }) {
  if (status === 'idle') return null
  return (
    <span
      className={cn(
        'size-2 shrink-0 rounded-full',
        status === 'running' ? 'bg-brand animate-pulse' : 'bg-destructive',
      )}
    />
  )
}

interface ConversationListProps {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  /** 删除只发起请求，确认弹窗归各容器持有（须挂 Popover 外避免 hover 收起连带卸载）。 */
  onRequestDelete: (id: string) => void
  /** 重命名。不给则不渲染改名入口（列表本身仍是纯展示，改不改名由容器决定）。 */
  onRename?: (id: string, title: string) => void
}

/**
 * 会话列表行（纯展示）
 *
 * 全局侧栏会话区（SidebarConversations）复用这份行渲染。
 * 不带自己的滚动容器与表头 —— 由容器套外层，高度/留白自定。
 */
export function ConversationList({
  conversations,
  currentId,
  onSelect,
  onRequestDelete,
  onRename,
}: ConversationListProps) {
  const statuses = useStreamStatusStore((s) => s.statuses)
  const titleOf = useConversationTitle()
  // 正在改名的那一行（null = 没有）。同时只允许一行处于编辑态
  const [editingId, setEditingId] = useState<string | null>(null)
  // 按更新时间倒序
  const sorted = [...conversations].sort(
    (a, b) => +new Date(b.updated_at) - +new Date(a.updated_at),
  )

  if (sorted.length === 0) {
    return (
      <div className="text-muted-foreground px-2 py-3 text-center text-xs">
        还没有对话
      </div>
    )
  }

  return (
    <>
      {sorted.map((c) => {
        const isActive = c.id === currentId

        // 编辑态：整行让位给输入框，其余控件（状态点 / 删除）先撤下，别抢点击
        if (editingId === c.id && onRename) {
          return (
            <RenameRow
              key={c.id}
              initial={titleOf(c)}
              onCommit={(title) => {
                setEditingId(null)
                if (title.trim() && title !== titleOf(c)) onRename(c.id, title)
              }}
              onCancel={() => setEditingId(null)}
            />
          )
        }

        return (
          <div
            key={c.id}
            className={cn(
              'group flex items-center gap-1 rounded-md pr-1',
              isActive ? 'bg-brand-subtle' : 'hover:bg-muted',
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(c.id)}
              className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left"
            >
              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    'truncate text-sm',
                    isActive && 'text-brand font-medium',
                  )}
                >
                  {/* 真标题 → 起名中的占位 → 新对话，三级回落 */}
                  {titleOf(c)}
                </div>
                <div className="text-muted-foreground text-[11px]">
                  {dayjs(c.updated_at).fromNow()}
                </div>
              </div>
              <StatusDot status={statuses[c.id] ?? 'idle'} />
              {isActive && <Check className="text-brand size-3.5 shrink-0" />}
            </button>
            {onRename && (
              <button
                type="button"
                aria-label="重命名对话"
                onClick={() => setEditingId(c.id)}
                className="text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 rounded p-1 opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100"
              >
                <Pencil className="size-3.5" />
              </button>
            )}
            <button
              type="button"
              aria-label="删除对话"
              onClick={() => onRequestDelete(c.id)}
              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0 rounded p-1 opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100"
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        )
      })}
    </>
  )
}

/**
 * 改名行 —— 一个占满整行的输入框。
 *
 * 提交时机三条：回车、失焦（点到别处即保存，跟 ChatGPT / VS Code 侧栏一致）、
 * Esc 取消。挂载即全选，用户直接打字就是覆盖，不用先清空。
 */
function RenameRow({
  initial,
  onCommit,
  onCancel,
}: {
  initial: string
  onCommit: (title: string) => void
  onCancel: () => void
}) {
  const [value, setValue] = useState(initial)
  const ref = useRef<HTMLInputElement>(null)
  // Esc 会先撤焦点、blur 跟着触发，若不设闸就会被当成「失焦保存」把取消吃掉
  const abandoned = useRef(false)

  useEffect(() => {
    ref.current?.select()
  }, [])

  return (
    <div className="px-1 py-0.5">
      <input
        ref={ref}
        autoFocus
        value={value}
        maxLength={200}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => {
          if (!abandoned.current) onCommit(value)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            abandoned.current = true // 提交走这条，别让随后的 blur 再提交一次
            onCommit(value)
          }
          if (e.key === 'Escape') {
            abandoned.current = true
            onCancel()
          }
        }}
        className="border-brand/40 focus-visible:ring-brand/30 w-full rounded-md border bg-transparent px-2 py-1.5 text-sm outline-none focus-visible:ring-2"
      />
    </div>
  )
}

interface DeleteConversationDialogProps {
  conversation: Conversation | undefined
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

/**
 * 删除对话二次确认弹窗
 *
 * 由各容器自己持有并挂在 Popover 外 —— 浮窗 hover 收起会卸载其内部子树，
 * 确认弹窗若挂在里面会被连带卸载，故下沉为独立组件供两处复用。
 */
export function DeleteConversationDialog({
  conversation,
  open,
  onOpenChange,
  onConfirm,
}: DeleteConversationDialogProps) {
  const titleOf = useConversationTitle()
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除这条对话？</AlertDialogTitle>
          <AlertDialogDescription>
            「{conversation ? titleOf(conversation) : '新对话'}
            」及其全部消息将被永久删除，无法恢复。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>
            删除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
