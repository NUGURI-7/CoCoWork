import { cn } from '@/lib/utils'

/** 名字 → 稳定色相（哈希派生，同名永远同色）。 */
function hueOf(name: string): number {
  let h = 0
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) % 360
  }
  return h
}

interface McpServerAvatarProps {
  /** 显示名，取首字母 + 哈希派生色 */
  name: string
  /** 边长 px */
  size?: number
  className?: string
}

/**
 * MCP server 头像：首字母 + 哈希派生彩色块。
 *
 * 不抓 favicon —— MCP server 多是 API 子域名（mcp.xxx.com），favicon 命中率
 * 极低，且 favicon 服务在「无图标」时返回的是丑默认图（不 404，降级失效）。
 * 色块固定不随主题变（同各类 app 的字母头像），light/dark 都清晰。
 */
export function McpServerAvatar({ name, size = 40, className }: McpServerAvatarProps) {
  const initial = name.trim().charAt(0).toUpperCase() || '?'
  const hue = hueOf(name)
  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-center rounded-md font-medium',
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.42,
        backgroundColor: `hsl(${hue} 50% 88%)`,
        color: `hsl(${hue} 50% 32%)`,
      }}
    >
      {initial}
    </div>
  )
}
