/** /workspaces/:workspaceId/new —— 新对话：网址不带会话 id，发出第一句话后换成 /c/:conversationId */
import { useCallback, useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { v4 as uuidv4 } from 'uuid'

import { useImmersiveStore } from '@/stores/immersive'
import { useWorkspaceShell } from '@/pages/workspaces/shell-context'
import { WorkspaceChat } from '@/pages/workspaces/WorkspaceChat'

export const Route = createFileRoute('/_authenticated/workspaces/$workspaceId/new')({
  component: NewConversationRoute,
})

function NewConversationRoute() {
  const { workspaceId } = Route.useParams()
  // 换空间时整块重挂，拿一个新的会话 id
  return <NewConversation key={workspaceId} workspaceId={workspaceId} />
}

function NewConversation({ workspaceId }: { workspaceId: string }) {
  const navigate = useNavigate()
  const { supervisorReady, notifyArtifacts } = useWorkspaceShell()
  const immersive = useImmersiveStore((s) => s.active)
  // 会话 id 在这里由前端生成；停留在本页期间不变，发出第一句话时后端用它建库
  const [conversationId] = useState(() => uuidv4())

  // 第一句话已发出：网址换成这条会话的地址（replace，不留 /new 这条历史）。
  // 对话状态按会话 id 存在常驻架子上，换页面后取回的是同一份，回复不会中断
  const handleStarted = useCallback(() => {
    navigate({
      to: '/workspaces/$workspaceId/c/$conversationId',
      params: { workspaceId, conversationId },
      replace: true,
    })
  }, [navigate, workspaceId, conversationId])

  return (
    <WorkspaceChat
      workspaceId={workspaceId}
      conversationId={conversationId}
      isNew
      onStarted={handleStarted}
      supervisorReady={supervisorReady}
      topFade={immersive}
      onArtifacts={notifyArtifacts}
    />
  )
}
