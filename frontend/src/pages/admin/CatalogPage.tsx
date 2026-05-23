import { useCallback, useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { ring } from 'ldrs'
import { toast } from 'sonner'

import { deleteCatalog, listCatalog } from '@/api/model'
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

/** /admin/settings/catalog — 模型目录管理 */
export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [confirmItem, setConfirmItem] = useState<CatalogItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listCatalog()
      setItems(data)
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
                <TableHead>供应商类型</TableHead>
                <TableHead>模型类型</TableHead>
                <TableHead>模型 ID</TableHead>
                <TableHead className="w-16 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
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

      <AddCatalogDialog open={addOpen} onOpenChange={setAddOpen} onCreated={refetch} />

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
              className="bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
