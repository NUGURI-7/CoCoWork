import { useEffect, useState } from 'react'
import { CheckCircle2, Plus, X, XCircle } from 'lucide-react'
import { toast } from 'sonner'

import {
  createMCPServer,
  testMCPConnection,
  updateMCPServer,
  type MCPTestConnectionResult,
} from '@/api/mcp'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { MCPServer, MCPTransport } from '@/types'

const transports: { value: MCPTransport; label: string }[] = [
  { value: 'streamable_http', label: 'Streamable HTTP（推荐）' },
  { value: 'sse', label: 'SSE（降级兼容）' },
]

interface HeaderRow {
  key: string
  value: string
}

interface CreateMcpServerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 传入则为编辑模式（预填基础字段；headers 不回传，留空不改） */
  editing?: MCPServer | null
  onSaved?: () => void
}

export function CreateMcpServerDialog({
  open,
  onOpenChange,
  editing,
  onSaved,
}: CreateMcpServerDialogProps) {
  const isEdit = !!editing

  const [name, setName] = useState('')
  const [serverUrl, setServerUrl] = useState('')
  const [transport, setTransport] = useState<MCPTransport>('streamable_http')
  const [headers, setHeaders] = useState<HeaderRow[]>([])
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<MCPTestConnectionResult | null>(
    null,
  )

  // 打开时按 editing 预填；headers 后端不回传，始终从空起（编辑时留空=不改）
  useEffect(() => {
    if (!open) return
    setName(editing?.name ?? '')
    setServerUrl(editing?.server_url ?? '')
    setTransport(editing?.transport ?? 'streamable_http')
    setDescription(editing?.description ?? '')
    setHeaders([])
    setSubmitting(false)
    setTesting(false)
    setTestResult(null)
  }, [open, editing])

  // 改了连接相关配置 → 上次测试结果作废
  useEffect(() => {
    setTestResult(null)
  }, [serverUrl, transport, headers])

  const canSubmit = name.trim() && serverUrl.trim()

  function setHeaderAt(i: number, patch: Partial<HeaderRow>) {
    setHeaders((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }
  function addHeader() {
    setHeaders((rows) => [...rows, { key: '', value: '' }])
  }
  function removeHeader(i: number) {
    setHeaders((rows) => rows.filter((_, idx) => idx !== i))
  }

  /** 非空行收集成 dict（key 去空白，空 key 行丢弃） */
  function collectHeaders(): Record<string, string> {
    const out: Record<string, string> = {}
    for (const { key, value } of headers) {
      const k = key.trim()
      if (k) out[k] = value
    }
    return out
  }

  async function handleTest() {
    if (!serverUrl.trim()) return
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testMCPConnection({
        server_url: serverUrl.trim(),
        transport,
        headers: collectHeaders(),
      })
      setTestResult(result)
    } catch {
      // silent：仅网络 / 500 才到这，给个兜底结果
      setTestResult({
        success: false,
        tool_count: 0,
        tools: [],
        error: '请求失败，请重试',
      })
    } finally {
      setTesting(false)
    }
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    const collected = collectHeaders()
    try {
      if (isEdit && editing) {
        await updateMCPServer(editing.id, {
          name: name.trim(),
          server_url: serverUrl.trim(),
          transport,
          description: description.trim(),
          // 留空不动已存鉴权头；填了则整体覆盖
          ...(Object.keys(collected).length ? { headers: collected } : {}),
        })
        toast.success('MCP server 已更新')
      } else {
        await createMCPServer({
          name: name.trim(),
          server_url: serverUrl.trim(),
          transport,
          headers: collected,
          description: description.trim(),
        })
        toast.success('MCP server 创建成功')
      }
      onOpenChange(false)
      onSaved?.()
    } catch (err) {
      const msg = err instanceof Error ? err.message : '保存失败'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? '编辑 MCP server' : '添加 MCP server'}
          </DialogTitle>
          <DialogDescription>
            配置外部 MCP server 的连接信息，请求头（含鉴权 token）将加密存储
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* 名称 */}
          <div className="grid gap-2">
            <Label htmlFor="mcp-name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="mcp-name"
              placeholder="如：高德地图"
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* Server URL */}
          <div className="grid gap-2">
            <Label htmlFor="mcp-url">
              Server URL <span className="text-destructive">*</span>
            </Label>
            <Input
              id="mcp-url"
              placeholder="https://mcp.example.com/sse"
              maxLength={1024}
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
            />
          </div>

          {/* 传输协议 */}
          <div className="grid gap-2">
            <Label>传输协议</Label>
            <Select
              value={transport}
              onValueChange={(v) => setTransport(v as MCPTransport)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {transports.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 请求头（动态行） */}
          <div className="grid gap-2">
            <Label>请求头（鉴权，可选）</Label>
            {headers.map((row, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  placeholder="Header（如 Authorization）"
                  value={row.key}
                  onChange={(e) => setHeaderAt(i, { key: e.target.value })}
                />
                <Input
                  placeholder="值（如 Bearer xxx）"
                  value={row.value}
                  onChange={(e) => setHeaderAt(i, { value: e.target.value })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground shrink-0"
                  onClick={() => removeHeader(i)}
                >
                  <X className="size-4" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="justify-self-start"
              onClick={addHeader}
            >
              <Plus className="size-4" />
              添加请求头
            </Button>
            {isEdit && (
              <p className="text-muted-foreground text-xs">
                留空则不修改已保存的请求头；填写则整体覆盖。
              </p>
            )}
          </div>

          {/* 描述 */}
          <div className="grid gap-2">
            <Label htmlFor="mcp-desc">描述</Label>
            <Textarea
              id="mcp-desc"
              placeholder="备注信息（可选）"
              maxLength={500}
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* 测试连接结果 */}
          {testResult && (
            <div
              className={
                testResult.success
                  ? 'border-brand-border bg-brand-subtle text-brand flex flex-col gap-1 rounded-md border px-3 py-2 text-sm'
                  : 'border-destructive/30 bg-destructive/5 text-destructive flex items-start gap-2 rounded-md border px-3 py-2 text-sm'
              }
            >
              {testResult.success ? (
                <>
                  <div className="flex items-center gap-2 font-medium">
                    <CheckCircle2 className="size-4 shrink-0" />
                    连接成功，发现 {testResult.tool_count} 个工具
                  </div>
                  {testResult.tools.length > 0 && (
                    <p className="text-brand/80 line-clamp-2 text-xs">
                      {testResult.tools.map((t) => t.name).join('、')}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <XCircle className="mt-0.5 size-4 shrink-0" />
                  <span className="break-all">
                    连接失败：{testResult.error || '未知错误'}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="sm:justify-between">
          <Button
            type="button"
            variant="outline"
            onClick={handleTest}
            disabled={!serverUrl.trim() || testing}
          >
            {testing ? '测试中...' : '测试连接'}
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={!canSubmit || submitting}>
              {submitting ? '保存中...' : isEdit ? '保存' : '创建'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
