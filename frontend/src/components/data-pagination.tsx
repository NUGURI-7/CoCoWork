/**
 * 通用分页器：基于 shadcn pagination 原子组件包装。
 *
 * 接 (page, totalPages, onPageChange) → 自动算页码窗口 + 渲染省略号。
 * 左侧可选 `共 N 条` 总数显示。
 */
import type { MouseEvent } from 'react'

import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { cn } from '@/lib/utils'

interface DataPaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  /** 总条数。传入则在左侧显示「共 N 条」 */
  total?: number
  className?: string
}

export function DataPagination({
  page,
  totalPages,
  onPageChange,
  total,
  className,
}: DataPaginationProps) {
  // 单页或无数据：只显示总数（如有），不渲染翻页器
  if (totalPages <= 1) {
    if (total === undefined) return null
    return (
      <div className={cn('text-muted-foreground text-xs', className)}>
        共 {total} 条
      </div>
    )
  }

  const items = computePageWindow(page, totalPages)

  const goto = (p: number) => (e: MouseEvent) => {
    e.preventDefault()
    if (p !== page && p >= 1 && p <= totalPages) onPageChange(p)
  }

  const prevDisabled = page <= 1
  const nextDisabled = page >= totalPages

  return (
    <div className={cn('flex items-center justify-between gap-4', className)}>
      {total !== undefined ? (
        <span className="text-muted-foreground text-xs">共 {total} 条</span>
      ) : (
        <span />
      )}

      <Pagination className="mx-0 w-auto justify-end">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              href="#"
              onClick={prevDisabled ? (e) => e.preventDefault() : goto(page - 1)}
              aria-disabled={prevDisabled}
              className={cn(prevDisabled && 'pointer-events-none opacity-50')}
            />
          </PaginationItem>

          {items.map((p, i) =>
            p === 'ellipsis' ? (
              <PaginationItem key={`e-${i}`}>
                <PaginationEllipsis />
              </PaginationItem>
            ) : (
              <PaginationItem key={p}>
                <PaginationLink href="#" isActive={p === page} onClick={goto(p)}>
                  {p}
                </PaginationLink>
              </PaginationItem>
            ),
          )}

          <PaginationItem>
            <PaginationNext
              href="#"
              onClick={nextDisabled ? (e) => e.preventDefault() : goto(page + 1)}
              aria-disabled={nextDisabled}
              className={cn(nextDisabled && 'pointer-events-none opacity-50')}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  )
}

/**
 * 算页码窗口（带省略号）：
 * - totalPages ≤ 7：全部展开
 * - 当前页靠左：[1 2 3 4 5 … N]
 * - 当前页靠右：[1 … N-4 N-3 N-2 N-1 N]
 * - 中间：[1 … P-1 P P+1 … N]
 */
function computePageWindow(
  page: number,
  totalPages: number,
): (number | 'ellipsis')[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1)
  }

  const nearLeft = page <= 4
  const nearRight = page >= totalPages - 3

  if (nearLeft) {
    return [1, 2, 3, 4, 5, 'ellipsis', totalPages]
  }
  if (nearRight) {
    return [
      1,
      'ellipsis',
      totalPages - 4,
      totalPages - 3,
      totalPages - 2,
      totalPages - 1,
      totalPages,
    ]
  }
  return [1, 'ellipsis', page - 1, page, page + 1, 'ellipsis', totalPages]
}
