/**
 * Axios 请求层 — 对接后端 backend/app/core/http/response.py 的统一响应壳。
 *
 * 约定：
 *  - 所有业务接口走 `/api/v1/*`（dev 由 vite proxy 转发到 :7999）
 *  - 后端始终 HTTP 200，业务错误码在 `ResponseModel.code`
 *  - 拦截器解包到 `payload.data`：业务代码 `await get<User>('/me')` 直接拿 User
 *  - 业务错误（code !== 200）抛 `ApiBusinessError`，HTTP / 网络错误抛 AxiosError
 *  - 默认 toast 错误；调用方可传 `{ silent: true }` 自行处理
 */

import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { toast } from 'sonner'
import type { ResponseModel } from '@/types'

// ============================================================================
// 类型增强：给 axios config 加 `silent` 字段
// ============================================================================
declare module 'axios' {
  interface AxiosRequestConfig {
    /** 跳过响应拦截器的默认错误 toast（业务代码自行处理） */
    silent?: boolean
  }
  interface InternalAxiosRequestConfig {
    silent?: boolean
  }
}

// ============================================================================
// 业务错误类：HTTP 200 但 ResponseModel.code !== 200
// ============================================================================
export class ApiBusinessError extends Error {
  code: number
  data: unknown

  constructor(payload: ResponseModel) {
    super(payload.message || '请求失败')
    this.name = 'ApiBusinessError'
    this.code = payload.code
    this.data = payload.data
  }
}

// ============================================================================
// Axios 实例
// ============================================================================
const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000, // 30s；流式 / 长任务接口业务自己 override
  withCredentials: false,
})

// ============================================================================
// 请求拦截器：注入 Authorization header
// ============================================================================
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!config.headers) {
      config.headers = new AxiosHeaders()
    }
    // 绝对 URL 跳过 token 注入（如打第三方 API）
    if (config.url?.startsWith('http')) {
      return config
    }
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`)
    }
    return config
  },
  (err: unknown) => Promise.reject(err),
)

// ============================================================================
// 响应拦截器：解包 ResponseModel + 双轨 toast + 401 自动登出
// ============================================================================
instance.interceptors.response.use(
  (response: AxiosResponse<ResponseModel>) => {
    const payload = response.data

    // 非 JSON 响应（如 Blob 下载）直接放行
    if (payload instanceof Blob || typeof payload !== 'object' || payload === null) {
      return response as unknown as AxiosResponse
    }

    // 业务错误
    if (payload.code !== 200) {
      if (!response.config.silent) {
        toast.error(payload.message || '请求失败')
      }
      return Promise.reject(new ApiBusinessError(payload))
    }

    // 成功：解包到 data 字段
    // 注意：这里返回的是 payload.data（T），但 axios 内部签名仍是 AxiosResponse
    // 通过下方辅助函数 get/post 的类型强转还原为 Promise<T>
    return payload.data as unknown as AxiosResponse
  },
  (err: AxiosError) => {
    const silent = err.config?.silent

    if (err.code === 'ECONNABORTED') {
      if (!silent) toast.error('请求超时，请重试')
    } else if (!err.response) {
      // 没有响应 = 网络断 / CORS 拦截 / proxy 没起来
      if (!silent) toast.error('网络连接失败')
    } else {
      const status = err.response.status
      if (status === 401) {
        // Token 过期 / 未登录：清 token 并跳登录页（避免在 /login 自身循环）
        localStorage.removeItem('token')
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
      } else if (!silent) {
        toast.error(`请求错误 (${status})`)
      }
    }

    return Promise.reject(err)
  },
)

// ============================================================================
// 辅助函数：泛型解包，调用方拿到的是 T（不是 AxiosResponse<T>）
// ============================================================================
export function get<T = unknown>(
  url: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.get(url, { ...config, params }) as unknown as Promise<T>
}

export function post<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.post(url, data, config) as unknown as Promise<T>
}

export function put<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.put(url, data, config) as unknown as Promise<T>
}

export function patch<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.patch(url, data, config) as unknown as Promise<T>
}

export function del<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return instance.delete(url, config) as unknown as Promise<T>
}

// 直接暴露实例，给特殊场景（如自定义 transformRequest / 流式响应）用
export { instance as request }
