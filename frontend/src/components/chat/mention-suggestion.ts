import { ReactRenderer } from '@tiptap/react'
import type {
  SuggestionKeyDownProps,
  SuggestionProps,
} from '@tiptap/suggestion'
import { computePosition, flip, offset, shift } from '@floating-ui/dom'

import {
  MentionList,
  type MentionItem,
  type MentionListRef,
} from './MentionList'

type Selected = { id: string; label: string }
type Props = SuggestionProps<MentionItem, Selected>

/**
 * 把 TipTap suggestion 的命令式生命周期桥接到 React 候选浮层。
 *
 * - items：读外部 getItems()（支持成员异步加载，char='@' 后按 query 过滤）
 * - render：onStart/onUpdate 用 ReactRenderer 渲染 MentionList，floating-ui 定位；
 *   onKeyDown 把上下键/回车转发给 MentionList（编辑器仍持焦点）；onExit 清理
 *
 * 定位用 @floating-ui/dom（依赖树已有，Radix 带的）：virtual reference = 光标 rect，
 * flip/shift 自动处理出界（默认浮在光标上方，空间不够翻到下方/收边）。
 */
export function createMentionSuggestion(
  getItems: () => MentionItem[],
  onActiveChange: (active: boolean) => void,
) {
  return {
    char: '@',
    items: ({ query }: { query: string }): MentionItem[] => {
      const q = query.toLowerCase()
      return getItems()
        .filter((i) => i.label.toLowerCase().includes(q))
        .slice(0, 8)
    },
    render: () => {
      let renderer: ReactRenderer<MentionListRef> | null = null

      const reposition = (clientRect: Props['clientRect']) => {
        const rect = clientRect?.()
        if (!renderer || !rect) return
        const el = renderer.element as HTMLElement
        void computePosition({ getBoundingClientRect: () => rect }, el, {
          placement: 'top-start',
          middleware: [offset(6), flip(), shift({ padding: 8 })],
        }).then(({ x, y }) => {
          el.style.left = `${x}px`
          el.style.top = `${y}px`
        })
      }

      return {
        onStart: (props: Props) => {
          onActiveChange(true)
          renderer = new ReactRenderer(MentionList, {
            props: { items: props.items, command: props.command },
            editor: props.editor,
          })
          const el = renderer.element as HTMLElement
          el.style.position = 'absolute'
          el.style.zIndex = '50'
          el.style.top = '0'
          el.style.left = '0'
          document.body.appendChild(el)
          reposition(props.clientRect)
        },
        onUpdate: (props: Props) => {
          renderer?.updateProps({ items: props.items, command: props.command })
          reposition(props.clientRect)
        },
        onKeyDown: (props: SuggestionKeyDownProps) => {
          if (props.event.key === 'Escape') return true
          return renderer?.ref?.onKeyDown({ event: props.event }) ?? false
        },
        onExit: () => {
          onActiveChange(false)
          renderer?.element.remove()
          renderer?.destroy()
          renderer = null
        },
      }
    },
  }
}
