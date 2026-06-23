import { createContext, useContext } from 'react'

/**
 * 工作空间外壳 → 对话子路由的共享上下文。
 *
 * 嵌套路由下，外壳（布局）持有 workspace，对话区是子路由（/c/$conversationId）。
 * 子路由从 path 参数拿 workspaceId / conversationId、自身读 store 的 immersive，
 * 唯独 supervisorReady 派生自 workspace（外壳才有），经此 Context 下发。
 */
interface WorkspaceShellValue {
  /** 管家是否已配 chat 模型 —— 决定对话区可不可发 */
  supervisorReady: boolean
}

export const WorkspaceShellContext = createContext<WorkspaceShellValue | null>(null)

export function useWorkspaceShell(): WorkspaceShellValue {
  const value = useContext(WorkspaceShellContext)
  if (!value) {
    throw new Error('useWorkspaceShell 必须在 WorkspaceShellContext.Provider 内使用')
  }
  return value
}
