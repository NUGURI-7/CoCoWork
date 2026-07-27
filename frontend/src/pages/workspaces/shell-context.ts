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
  /**
   * 对话里产出了新文件时叫一声，外壳据此让产出物面板重拉。
   *
   * 只往上送信号、不送数据：产物本体走接口，面板始终只有一个数据来源。
   */
  notifyArtifacts: () => void
}

export const WorkspaceShellContext = createContext<WorkspaceShellValue | null>(null)

export function useWorkspaceShell(): WorkspaceShellValue {
  const value = useContext(WorkspaceShellContext)
  if (!value) {
    throw new Error('useWorkspaceShell 必须在 WorkspaceShellContext.Provider 内使用')
  }
  return value
}
