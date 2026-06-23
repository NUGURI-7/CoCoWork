/** /workspaces/:workspaceId —— 无会话落点：外壳 effect 会 replace 跳到最近一条会话 */
import { createFileRoute } from '@tanstack/react-router'
import { ring } from 'ldrs'

ring.register()

export const Route = createFileRoute('/_authenticated/workspaces/$workspaceId/')({
  component: ConversationIndex,
})

function ConversationIndex() {
  // 跳转前的极短占位（外壳已渲染四周，只有对话区这一格在等重定向）
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center">
      <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
    </div>
  )
}
