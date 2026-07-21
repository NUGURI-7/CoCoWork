/**
 * 柔和分类色板 —— 按 seed 确定性映射到一套淡彩底 + 深色字。
 *
 * 「确定性」：同一 seed（如 workspace.id / 成员名）永远得到同一颜色，
 * 刷新不变色；视觉上像随机，实则稳定可控。
 *
 * 全项目唯一色板源：头像占位（WorkspaceAvatar）、子 Agent pill
 * （DelegateBlock）共用，跟品牌墨绿和谐，自带 dark: variant 适配深色模式。
 */

/** 柔和 categorical 色板 —— 与 DelegateBlock pill 同款：bg-*-50 浅底 + text-*-800 深字。 */
const PALETTE = [
  'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200',
  'bg-violet-50 text-violet-800 dark:bg-violet-950/60 dark:text-violet-200',
  'bg-orange-50 text-orange-800 dark:bg-orange-950/60 dark:text-orange-200',
  'bg-sky-50 text-sky-800 dark:bg-sky-950/60 dark:text-sky-200',
  'bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-200',
  'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-200',
] as const

/** 轻量字符串 hash（djb2 变体）→ 非负整数。 */
function hashSeed(seed: string): number {
  let hash = 5381
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 33) ^ seed.charCodeAt(i)
  }
  return hash >>> 0
}

/** seed → 柔和底色的 Tailwind 类名（bg + text，含 dark variant）。 */
export function softPalette(seed: string): string {
  return PALETTE[hashSeed(seed) % PALETTE.length]
}
