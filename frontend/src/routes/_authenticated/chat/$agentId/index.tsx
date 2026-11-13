/** /chat/:agentId —— 无会话落点：外壳 effect 会跳到最近一条会话，没有会话就跳新对话页 */
import { createFileRoute } from '@tanstack/react-router'
import { ring } from 'ldrs'

ring.register()

export const Route = createFileRoute('/_authenticated/chat/$agentId/')({
  component: () => (
    <div className="flex min-h-0 flex-1 items-center justify-center">
      <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
    </div>
  ),
})
