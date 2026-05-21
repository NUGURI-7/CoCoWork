/**
 * 后端统一响应壳 — 对齐 backend/app/core/http/response.py
 *
 * 约定：HTTP 状态码始终 200，业务错误码放在 `code` 字段（DaisyWind 沿用风格）。
 * 拦截器根据 code 判断成功 / 失败，前端业务代码只拿 `data`。
 */
export interface ResponseModel<T = unknown> {
  code: number
  message: string
  data: T | null
}

/**
 * 分页数据 payload — 对齐 backend PageData。
 *
 * 字段命名沿用 DaisyWind 中式：records / current_page / page_size，不是 items / page。
 */
export interface PageData<T> {
  total: number
  records: T[]
  current_page: number
  page_size: number
}

/** 分页响应的完整壳 */
export type PageResponse<T> = ResponseModel<PageData<T>>
