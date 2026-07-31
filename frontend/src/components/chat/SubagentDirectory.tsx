import { createContext, useContext, type ReactNode } from 'react'

/**
 * 派活成员目录 —— 把后端的 subagent 戳（member_xxx 技术 id）映射成可展示的真名 / 头像。
 *
 * chat 层是通用的（Playground / Workspace 共用），不该绑 workspace 成员概念，
 * 所以这里只提供「接口」：DelegateBlock 通过 useSubagentInfo 查名。
 * 由 workspace 在 WorkspaceChat 外层用真实成员名册填充；Playground 不填，DelegateBlock 降级显示原始 id。
 */
export interface SubagentInfo {
  name: string
  avatarUrl?: string
}

const SubagentDirectoryContext = createContext<Record<string, SubagentInfo>>({})

export function SubagentDirectoryProvider({
  value,
  children,
}: {
  value: Record<string, SubagentInfo>
  children: ReactNode
}) {
  return (
    <SubagentDirectoryContext.Provider value={value}>
      {children}
    </SubagentDirectoryContext.Provider>
  )
}

/** subagentName（member_xxx）→ 展示信息；未注册返回 undefined，调用方自行降级。 */
export function useSubagentInfo(subagentName: string): SubagentInfo | undefined {
  return useContext(SubagentDirectoryContext)[subagentName]
}

/** 整本名册 —— 一次要查多个时用（如逐行标注派活消耗，hook 不能进循环）。 */
export function useSubagentDirectory(): Record<string, SubagentInfo> {
  return useContext(SubagentDirectoryContext)
}
