/** /workspaces/:workspaceId/c/:conversationId —— 对话子路由 */
import { createFileRoute } from '@tanstack/react-router'

import { useImmersiveStore } from '@/stores/immersive'
import { useWorkspaceShell } from '@/pages/workspaces/shell-context'
import { WorkspaceChat } from '@/pages/workspaces/WorkspaceChat'

export const Route = createFileRoute('/_authenticated/workspaces/$workspaceId/c/$conversationId')({
  component: ConversationRoute,
})

function ConversationRoute() {
  const { workspaceId, conversationId } = Route.useParams()
  const { supervisorReady } = useWorkspaceShell()
  const immersive = useImmersiveStore((s) => s.active)

  // key=conversationId：切会话整块重挂（重新拉历史 / 从 registry 取对应桶），沿用原 key 语义
  return (
    <WorkspaceChat
      key={conversationId}
      workspaceId={workspaceId}
      conversationId={conversationId}
      supervisorReady={supervisorReady}
      topFade={immersive}
    />
  )
}
