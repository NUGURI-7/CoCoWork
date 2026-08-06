/**
 * 知识库 API — 对接 backend/app/api/routes/knowledge/knowledge_base.py
 *
 * 路径前缀 `/knowledge-bases`，加上 axios baseURL `/api/v1`。
 */

import { del, get, post, put } from '@/request'
import type {
  BatchProcessResult,
  Document,
  KnowledgeBase,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseUpdatePayload,
  PageData,
  ParseBackend,
  RetrievalMode,
  RetrievalTestResult,
  UploadInitOut,
} from '@/types'

/** 列出当前用户的知识库。 */
export function listKnowledgeBases() {
  return get<KnowledgeBase[]>('/knowledge-bases')
}

/**
 * 这台机器上可用的文档解析后端。
 *
 * Key 配在后端 .env 里，前端看不见，只能问。返回的是「配了凭证的」，
 * 不代表上游此刻通不通——建库表单不该卡在别人家服务的响应时间上。
 */
export function getParseBackends() {
  return get<ParseBackend[]>('/knowledge-bases/parse-backends')
}

/** 获取单个知识库详情。 */
export function getKnowledgeBase(id: string) {
  return get<KnowledgeBase>(`/knowledge-bases/${id}`)
}

/**
 * 创建知识库。走 silent 由表单层 toast。
 */
export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return post<KnowledgeBase>('/knowledge-bases', payload, { silent: true })
}

/**
 * 更新知识库（部分更新；不可改 embedding 模型）。走 silent 由表单层 toast。
 */
export function updateKnowledgeBase(id: string, payload: KnowledgeBaseUpdatePayload) {
  return put<KnowledgeBase>(`/knowledge-bases/${id}`, payload, { silent: true })
}

/** 删除知识库。失败走默认拦截器 toast（与 model 模块删除约定一致）。 */
export function deleteKnowledgeBase(id: string) {
  return del<null>(`/knowledge-bases/${id}`)
}

// ============================================================================
// Document — 文档元数据 CRUD + 下载
// ============================================================================

/** 列出某知识库下的文档（按 created_at 倒序）。 */
export function listDocuments(kbId: string) {
  return get<Document[]>(`/knowledge-bases/${kbId}/documents`)
}

/** 分页列出某知识库下的文档（按 created_at 倒序）。 */
export function listDocumentsPaginated(
  kbId: string,
  params: { page?: number; page_size?: number } = {},
) {
  return get<PageData<Document>>(`/knowledge-bases/${kbId}/documents/page`, params)
}

/** 删除文档（后端联动清 storage 对象 + ORM 级联清段/向量）。 */
export function deleteDocument(kbId: string, docId: string) {
  return del<null>(`/knowledge-bases/${kbId}/documents/${docId}`)
}

/**
 * 获取文档下载 URL。
 *
 * 后端两种存储后端返的形态不同，本函数统一成「拿到就能用」：
 * - R2 → 绝对 URL（对象存储直链），原样返回
 * - Local → 相对路径 `/knowledge-bases/.../raw`，这里补上 API 前缀
 */
export async function getDocumentDownloadUrl(
  kbId: string,
  docId: string,
): Promise<string> {
  const { url } = await get<{ url: string }>(
    `/knowledge-bases/${kbId}/documents/${docId}/download-url`,
  )
  return url.startsWith('http') ? url : `/api/v1${url}`
}

// ============================================================================
// Document — 上传三段式
// ============================================================================

/** 上传 init 请求体（前端声明的文件名 + 大小，后端从 name 解析扩展名） */
export interface UploadInitPayload {
  name: string
  size: number
}

/**
 * 发起上传：建 pending document、按存储后端返不同 strategy。
 * 走 silent 由调用方按字段失败 toast，避免一次上传里 init 失败被通用 toast 顶替。
 */
export function initDocumentUpload(kbId: string, payload: UploadInitPayload) {
  return post<UploadInitOut>(
    `/knowledge-bases/${kbId}/documents/upload-init`,
    payload,
    { silent: true },
  )
}

/** 通知后端 R2 直传完成（head 验对象在 + mark uploaded）。 */
export function confirmDocumentUpload(kbId: string, docId: string) {
  return post<null>(
    `/knowledge-bases/${kbId}/documents/${docId}/upload-complete`,
    undefined,
    { silent: true },
  )
}

/** 触发文档处理管线（向量化）。后端 BackgroundTasks 跑，立即返回，前端轮询看状态。 */
export function triggerProcessDocument(kbId: string, docId: string) {
  return post<Document>(
    `/knowledge-bases/${kbId}/documents/${docId}/process`,
    undefined,
    { silent: true },
  )
}

/**
 * 批量触发向量化。返回 triggered / skipped 两组 id（skipped = 状态不允许）。
 * silent：由调用方按 triggered/skipped 自定义 toast（部分成功语义）。
 */
export function batchProcessDocuments(kbId: string, documentIds: string[]) {
  return post<BatchProcessResult>(
    `/knowledge-bases/${kbId}/documents/batch-process`,
    { document_ids: documentIds },
    { silent: true },
  )
}

/** 批量删除文档（联动清 storage + 级联清段/向量）。返回实际删除数。 */
export function batchDeleteDocuments(kbId: string, documentIds: string[]) {
  return post<{ deleted: number }>(
    `/knowledge-bases/${kbId}/documents/batch-delete`,
    { document_ids: documentIds },
  )
}

/**
 * Local 模式：把文件 multipart POST 给后端 `upload-endpoint`。
 *
 * 走 axios（自带 onUploadProgress），passthrough endpoint 是 init 返的相对路径，
 * axios 自动拼 baseURL `/api/v1`。
 */
export function uploadDocumentPassthrough(
  uploadEndpoint: string,
  file: File,
  onProgress?: (ratio: number) => void,
) {
  const form = new FormData()
  form.append('file', file)
  return post<null>(uploadEndpoint, form, {
    silent: true,
    onUploadProgress: (e) => {
      if (e.total && onProgress) onProgress(e.loaded / e.total)
    },
  })
}

/**
 * R2 模式：把文件直接 PUT 到 R2 预签名 URL。
 *
 * 用裸 XHR 而非 fetch 的原因：fetch 不支持 upload progress（标准缺口）；
 * 用裸 XHR 而非 axios 的原因：axios 拦截器会尝试解包 ResponseModel，但 R2 返
 * 的是空体，会触发误报。直接 XHR 最稳。
 *
 * `expectedHeaders` 必须跟 init 时签名带的 Content-Type 一致，否则 R2 拒收。
 */
export function uploadDocumentToR2(
  uploadUrl: string,
  file: File,
  expectedHeaders: Record<string, string>,
  onProgress?: (ratio: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', uploadUrl)
    for (const [k, v] of Object.entries(expectedHeaders)) {
      xhr.setRequestHeader(k, v)
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else reject(new Error(`R2 上传失败（HTTP ${xhr.status}）`))
    }
    xhr.onerror = () => reject(new Error('网络错误，R2 上传中断'))
    xhr.send(file)
  })
}

// ============================================================================
// 检索 / 命中测试
// ============================================================================

/** 命中测试（语义检索）：返回命中段 + 相似度 + 四段耗时，不落库。
 *
 * 检索参数由调用方给全 —— **后端不会去读知识库上配的默认值**：
 * `mode` 不传按 vector 走、`rerankModelId` 不传就是不做精排。
 * 要复现「agent 实际拿到什么」，得把库上配的值显式传进来。
 */
export function retrievalTest(
  kbId: string,
  params: {
    query: string
    topK: number
    mode?: RetrievalMode
    /** 传模型 id = 开精排；不传 / null = 不开 */
    rerankModelId?: string | null
  },
) {
  return post<RetrievalTestResult>(`/knowledge-bases/${kbId}/retrieval-test`, {
    query: params.query,
    top_k: params.topK,
    ...(params.mode && { mode: params.mode }),
    ...(params.rerankModelId && { rerank_model_id: params.rerankModelId }),
  })
}
