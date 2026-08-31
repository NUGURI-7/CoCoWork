/**
 * 工具块的共享展示逻辑 —— ToolUseBlock（单个工具）与 FileOpsBlock（成组文件操作）共用。
 *
 * 这两个组件渲染的是同一批 SSE 事件（tool_use_*），只是按工具名分了两种形态，
 * 所以「叫什么名字、拿哪个参数当摘要、路径怎么缩短」这三件事必须是同一份，
 * 否则同一个工具在两处显示不一致。
 */

/**
 * 归入「文件操作」那一类的工具名。
 *
 * 来自 deepagents 的 FilesystemMiddleware，挂了 skill 的 agent 才有。它们是
 * skill 执行过程中的路径噪音——一次回复里能刷十几条，单条不携带用户关心的信息，
 * 所以合并成一条活动行（FileOpsBlock），而不是各占一张卡片。
 *
 * **execute 刻意不在内**：同样来自那个 middleware，但它是「agent 到底干了什么」
 * 的唯一可见处，值一张自己的卡片，继续走 ToolUseBlock。
 */
const FILE_OP_TOOLS = new Set([
  'ls',
  'read_file',
  'write_file',
  'edit_file',
  'glob',
  'grep',
])

export function isFileOpTool(name: string): boolean {
  return FILE_OP_TOOLS.has(name)
}

/** 工具名 → 中文（**纯展示**，模型看到的仍是英文原名）。 */
export const TOOL_LABELS: Record<string, string> = {
  ls: '列出目录',
  read_file: '读取文件',
  write_file: '写入文件',
  edit_file: '编辑文件',
  glob: '查找文件',
  grep: '搜索内容',
  execute: '执行命令',
}

/** 折叠时跟在工具名后面显示的那个参数 —— 一眼看出「对谁做的」。 */
export const PRIMARY_ARG: Record<string, string> = {
  ls: 'path',
  read_file: 'file_path',
  write_file: 'file_path',
  edit_file: 'file_path',
  glob: 'pattern',
  grep: 'pattern',
  execute: 'command',
}

export const SUMMARY_MAX = 56

/**
 * 把沙箱里的绝对路径缩短成「从挂载点起算」的形态。
 *
 * 本地沙箱是宿主机长路径、容器里是 /workspace/x，同一条规则两边都成立：
 * 只保留最后一个 workspace/ | skills/ | tmp/ 之后的部分。容器那条本就短，
 * 截了约等于没截 —— 故不必按环境分支。
 *
 * 只用于折叠头部；展开的参数区保留完整原文（要复制路径去打开文件时用）。
 */
export function shortenSandboxPaths(text: string): string {
  return text.replace(
    /(?:\/[^\s/]+)*\/((?:workspace|skills|tmp)\/[^\s]*)/g,
    '$1',
  )
}

/**
 * 从流式累积的 partial JSON 里取主参数，缩短 + 限长成一行摘要。
 *
 * 流式中途 JSON 还不完整（解析失败）时返回空串 —— 调用方据此不渲染摘要位，
 * 等参数收齐了自然浮现，不做「解析中…」这类会闪一下的中间态。
 */
export function primaryArgSummary(
  name: string,
  partialInputJson: string,
  max: number = SUMMARY_MAX,
): string {
  const key = PRIMARY_ARG[name]
  if (!key || !partialInputJson) return ''
  try {
    const value = JSON.parse(partialInputJson)?.[key]
    if (typeof value !== 'string') return ''
    const short = shortenSandboxPaths(value)
    return short.length > max ? `${short.slice(0, max)}…` : short
  } catch {
    return ''
  }
}
