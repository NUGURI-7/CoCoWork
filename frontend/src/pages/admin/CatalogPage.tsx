import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Search, Trash2 } from 'lucide-react'
import { ring } from 'ldrs'
import { toast } from 'sonner'

import { batchDeleteCatalog, deleteCatalog, listCatalog } from '@/api/model'
import { DataPagination } from '@/components/data-pagination'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { CatalogItem } from '@/types'
import { AddCatalogDialog } from './AddCatalogDialog'

ring.register()

const providerTypeLabel: Record<string, string> = {
  openai: 'OpenAI',
  dashscope: '阿里云百炼',
  siliconflow: '硅基流动',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  custom: '自定义',
}

const modelTypeLabel: Record<string, string> = {
  chat: '对话',
  embedding: '向量',
  rerank: '重排序',
  vision: '视觉',
  tts: '语音合成',
  stt: '语音识别',
  image: '图像',
  multimodal: '多模态',
}

const ALL = 'all'
const PAGE_SIZE = 20

/** /admin/settings/catalog — 模型目录管理 */
export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [confirmItem, setConfirmItem] = useState<CatalogItem | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [providerFilter, setProviderFilter] = useState(ALL)
  const [typeFilter, setTypeFilter] = useState(ALL)
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchConfirm, setBatchConfirm] = useState(false)

  // 筛选项只列数据里真实出现过的值，避免给出选了必然为空的选项
  const providerOptions = useMemo(
    () => [...new Set(items.map((i) => i.provider_type))].sort(),
    [items],
  )
  const typeOptions = useMemo(
    () => [...new Set(items.map((i) => i.model_type))].sort(),
    [items],
  )

  const visibleItems = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    return items.filter(
      (i) =>
        (providerFilter === ALL || i.provider_type === providerFilter) &&
        (typeFilter === ALL || i.model_type === typeFilter) &&
        (kw === '' || i.model_id.toLowerCase().includes(kw)),
    )
  }, [items, keyword, providerFilter, typeFilter])

  // 筛选变化 / 删到本页空了都会让当前页号越界，与其用 effect 回写 page
  // 再多渲染一轮，不如每次取值时就夹在合法区间内
  const totalPages = Math.max(1, Math.ceil(visibleItems.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pagedItems = visibleItems.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  // 表头勾选框作用于「当前筛选结果全部」而非当前页：这页的用途就是筛出一批
  // 一次删掉，按页全选会逼着用户翻十几页各勾一次
  const allVisibleSelected =
    visibleItems.length > 0 && visibleItems.every((i) => selected.has(i.id))

  function toggleAllVisible() {
    setSelected((prev) => {
      const next = new Set(prev)
      if (allVisibleSelected) visibleItems.forEach((i) => next.delete(i.id))
      else visibleItems.forEach((i) => next.add(i.id))
      return next
    })
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listCatalog()
      setItems(data)
      // 选中项按 id 记，重新拉表后已消失的 id 要清掉，否则批量删会带上幽灵 id
      setSelected((prev) => {
        const alive = new Set(data.map((i) => i.id))
        return new Set([...prev].filter((id) => alive.has(id)))
      })
    } catch {
      // 拦截器已 toast
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  async function handleDelete() {
    if (!confirmItem) return
    setDeleting(true)
    try {
      await deleteCatalog(confirmItem.id)
      toast.success('目录条目已删除')
      setConfirmItem(null)
      refetch()
    } catch {
      // 拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  async function handleBatchDelete() {
    setDeleting(true)
    try {
      const { deleted } = await batchDeleteCatalog([...selected])
      toast.success(`已删除 ${deleted} 个条目`)
      setBatchConfirm(false)
      refetch()
    } catch {
      // 拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold">模型目录</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            维护平台可选用的上游模型清单，用户创建模型时从中挑选
          </p>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="size-4" />
          添加条目
        </Button>
      </div>

      {!loading && items.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
            <Input
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value)
                setPage(1)
              }}
              placeholder="搜索模型 ID"
              className="pl-8"
            />
          </div>

          <Select
            value={providerFilter}
            onValueChange={(v) => {
              setProviderFilter(v)
              setPage(1)
            }}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="供应商" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部供应商</SelectItem>
              {providerOptions.map((p) => (
                <SelectItem key={p} value={p}>
                  {providerTypeLabel[p] ?? p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={typeFilter}
            onValueChange={(v) => {
              setTypeFilter(v)
              setPage(1)
            }}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部类型</SelectItem>
              {typeOptions.map((t) => (
                <SelectItem key={t} value={t}>
                  {modelTypeLabel[t] ?? t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <span className="text-muted-foreground shrink-0 text-sm tabular-nums">
            {visibleItems.length} / {items.length}
          </span>

          {selected.size > 0 && (
            <>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setBatchConfirm(true)}
              >
                <Trash2 className="size-4" />
                删除选中 {selected.size} 条
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelected(new Set())}
              >
                取消选择
              </Button>
            </>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <l-ring size="36" stroke="3" speed="2" color="#2f6b53" />
        </div>
      ) : items.length === 0 ? (
        <div className="border-border/60 text-muted-foreground flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-sm">
          <p>目录为空</p>
          <p className="mt-1 text-xs">点击右上角「添加条目」录入可用模型</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={allVisibleSelected}
                    onCheckedChange={toggleAllVisible}
                    aria-label="全选当前筛选结果"
                  />
                </TableHead>
                <TableHead>供应商类型</TableHead>
                <TableHead>模型类型</TableHead>
                <TableHead>模型 ID</TableHead>
                <TableHead className="w-16 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleItems.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-muted-foreground py-12 text-center text-sm"
                  >
                    没有匹配的条目
                  </TableCell>
                </TableRow>
              )}
              {pagedItems.map((item) => (
                <TableRow
                  key={item.id}
                  data-state={selected.has(item.id) ? 'selected' : undefined}
                >
                  <TableCell>
                    <Checkbox
                      checked={selected.has(item.id)}
                      onCheckedChange={() => toggleOne(item.id)}
                      aria-label={`选择 ${item.model_id}`}
                    />
                  </TableCell>
                  <TableCell>
                    {providerTypeLabel[item.provider_type] ?? item.provider_type}
                  </TableCell>
                  <TableCell>
                    {modelTypeLabel[item.model_type] ?? item.model_type}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{item.model_id}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-muted-foreground hover:text-destructive size-7"
                      onClick={() => setConfirmItem(item)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {!loading && items.length > 0 && (
        <DataPagination
          page={safePage}
          totalPages={totalPages}
          onPageChange={setPage}
          className="justify-end"
        />
      )}

      <AddCatalogDialog open={addOpen} onOpenChange={setAddOpen} onCreated={refetch} />

      <AlertDialog open={batchConfirm} onOpenChange={setBatchConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除选中的 {selected.size} 个条目？</AlertDialogTitle>
            <AlertDialogDescription>
              将从目录中批量移除这些条目，已创建的模型实例不受影响。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault()
                handleBatchDelete()
              }}
              variant="destructive"
            >
              {deleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={confirmItem !== null}
        onOpenChange={(v) => !v && setConfirmItem(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除目录条目？</AlertDialogTitle>
            <AlertDialogDescription>
              将从目录中移除「{confirmItem?.model_id}」，已创建的模型实例不受影响。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              variant="destructive"
            >
              {deleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
