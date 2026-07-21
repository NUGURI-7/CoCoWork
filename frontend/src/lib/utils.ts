import type { ClassValue } from 'clsx'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind class lists with conflict resolution.
 *
 * - `clsx` handles conditional / array / object class composition
 * - `twMerge` resolves conflicts (e.g. `px-2 px-4` → `px-4`)
 *
 * Required by shadcn/ui generated components.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
