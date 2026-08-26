import { memo, useEffect, useMemo, useState } from 'react'
import { ChevronDown, Wrench, XCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ToolUseBlock as ToolUseBlockType } from '@/types'

interface ToolUseBlockProps {
  block: ToolUseBlockType
}

/**
 * 工具名 → 中文（**纯展示**，模型看到的仍是英文原名）。
 *
 * 这七个来自 deepagents 的 FilesystemMiddleware，挂了 skill 的 agent 才有；
 * 它们不走本项目 CoCoTool 基类，所以没有后端下发的 display_name，只能前端映射。
 * 表里没有的工具（内置工具 / MCP）原样显示英文名。
 */
const TOOL_LABELS: Record<string, string> = {
  ls: '列出目录',
  read_file: '读取文件',
  write_file: '写入文件',
  edit_file: '编辑文件',
  glob: '查找文件',
  grep: '搜索内容',
  execute: '执行命令',
}

/** 折叠时跟在工具名后面显示的那个参数 —— 一眼看出「对谁做的」。 */
const PRIMARY_ARG: Record<string, string> = {
  ls: 'path',
  read_file: 'file_path',
  write_file: 'file_path',
  edit_file: 'file_path',
  glob: 'pattern',
  grep: 'pattern',
  execute: 'command',
}

const SUMMARY_MAX = 56

/**
 * 把沙箱里的绝对路径缩短成「从挂载点起算」的形态。
 *
 * 本地沙箱是宿主机长路径、容器里是 /workspace/x，同一条规则两边都成立：
 * 只保留最后一个 workspace/ | skills/ | tmp/ 之后的部分。容器那条本就短，
 * 截了约等于没截 —— 故不必按环境分支。
 *
 * 只用于折叠头部；展开的参数区保留完整原文（要复制路径去打开文件时用）。
 */
function shortenSandboxPaths(text: string): string {
  return text.replace(
    /(?:\/[^\s/]+)*\/((?:workspace|skills|tmp)\/[^\s]*)/g,
    '$1',
  )
}

/**
 * Tool 调用块 —— assistant tool_use 状态机渲染（building → calling → success/error）。
 *
 * 头部：状态图标 + 工具名 + 折叠箭头
 * 展开：参数（partial_json 美化）+ 结果（resultData 美化、非空才显）
 *
 * 折叠：local state + initial = block.collapsed；status 从运行态变终态时
 * 自动折叠（执行完成默认收起、用户已经看到参数 / 结果浮现过）。
 */
export const ToolUseBlock = memo(function ToolUseBlock({
  block,
}: ToolUseBlockProps) {
  const [collapsed, setCollapsed] = useState(block.collapsed)

  useEffect(() => {
    if (block.status === 'success' || block.status === 'error') {
      setCollapsed(true)
    }
  }, [block.status])

  const inputJsonText = useMemo(() => {
    const raw = block.partialInputJson
    if (!raw) return '(无参数)'
    try {
      return JSON.stringify(JSON.parse(raw), null, 2)
    } catch {
      return raw
    }
  }, [block.partialInputJson])

  /** 折叠头部的一行摘要：主参数缩短 + 限长。流式中途 JSON 还不完整时留空。 */
  const summary = useMemo(() => {
    const key = PRIMARY_ARG[block.name]
    if (!key || !block.partialInputJson) return ''
    try {
      const value = JSON.parse(block.partialInputJson)?.[key]
      if (typeof value !== 'string') return ''
      const short = shortenSandboxPaths(value)
      return short.length > SUMMARY_MAX
        ? `${short.slice(0, SUMMARY_MAX)}…`
        : short
    } catch {
      return ''
    }
  }, [block.name, block.partialInputJson])

  const resultText = useMemo(() => {
    const d = block.resultData
    if (d === null || d === undefined) return ''
    if (typeof d === 'string') return d
    try {
      return JSON.stringify(d, null, 2)
    } catch {
      return String(d)
    }
  }, [block.resultData])

  const hasResult = block.resultData !== null && block.resultData !== undefined

  // 状态色：success 品牌绿、error 红、running 走 muted（同色一行，扳手 + 工具名整体）
  const statusColor =
    block.status === 'success'
      ? 'text-brand'
      : block.status === 'error'
        ? 'text-destructive'
        : 'text-muted-foreground'

  return (
    <div className="max-w-full self-start">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className={cn(
          '-mx-1 inline-flex max-w-full cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm transition-colors',
          statusColor,
        )}
      >
        <span className="flex shrink-0 items-center">
          {block.status === 'error' ? (
            <XCircle size={14} />
          ) : (
            <Wrench size={14} />
          )}
        </span>

        <span className="shrink-0 font-medium">
          {block.displayName ?? TOOL_LABELS[block.name] ?? block.name}
        </span>

        {summary && (
          <span className="text-muted-foreground/70 min-w-0 truncate font-mono text-xs">
            {summary}
          </span>
        )}

        <ChevronDown
          size={12}
          className={cn(
            'shrink-0 opacity-60 transition-transform duration-200',
            collapsed && '-rotate-90',
          )}
        />
      </button>

      {!collapsed && (
        <div className="bg-muted/50 mt-1.5 ml-5 space-y-2 rounded-md p-3 text-xs">
          <div>
            <div className="text-muted-foreground mb-1">参数</div>
            <pre className="bg-background/60 overflow-x-auto rounded p-2 break-words whitespace-pre-wrap">
              {inputJsonText}
            </pre>
          </div>

          {hasResult && (
            <div>
              <div className="text-muted-foreground mb-1">结果</div>
              <pre className="bg-background/60 max-h-64 overflow-x-auto rounded p-2 break-words whitespace-pre-wrap">
                {resultText}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
})
