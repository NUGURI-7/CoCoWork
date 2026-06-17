import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { MoreHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { deleteProvider } from '@/api/model'
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
import { Card, CardContent } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import type { Provider } from '@/types'

/** Provider 类型 → 中文标签 */
const providerTypeLabel: Record<string, string> = {
  openai: 'OpenAI',
  dashscope: '阿里云百炼',
  siliconflow: '硅基流动',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  custom: '自定义',
}

/** Provider 类型 → 品牌色 */
const providerDotColor: Record<string, string> = {
  openai: 'bg-emerald-500',
  dashscope: 'bg-orange-500',
  siliconflow: 'bg-violet-500',
  deepseek: 'bg-blue-500',
  anthropic: 'bg-amber-600',
  custom: 'bg-gray-400',
}

interface ProviderCardProps {
  provider: Provider
  onDeleted?: () => void
}

export function ProviderCard({ provider, onDeleted }: ProviderCardProps) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  function handleClick() {
    navigate({ to: '/models/$providerId', params: { providerId: provider.id } })
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteProvider(provider.id)
      toast.success('供应商已删除')
      // 关掉本供应商详情标签（若开着），避免残留死链
      useWorkspaceTabsStore.getState().close(`/models/${provider.id}`)
      setConfirmOpen(false)
      onDeleted?.()
    } catch {
      // 默认拦截器已 toast
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Card
        className="card-interactive min-h-[150px]"
        onClick={handleClick}
      >
        <CardContent className="flex flex-1 flex-col justify-between gap-3">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground flex items-center gap-1.5 text-xs">
              <span
                className={`inline-block size-2 rounded-full ${providerDotColor[provider.provider_type] ?? 'bg-gray-400'}`}
              />
              {providerTypeLabel[provider.provider_type] ?? provider.provider_type}
            </span>
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-foreground -mr-1 -mt-1 size-6"
                  >
                    <MoreHorizontal className="size-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={(e) => {
                      e.preventDefault()
                      setConfirmOpen(true)
                    }}
                  >
                    <Trash2 className="size-4" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-medium leading-none">{provider.name}</h3>
            <p className="text-muted-foreground mt-1.5 line-clamp-2 text-sm">
              {provider.description || ' '}
            </p>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除供应商「{provider.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销，关联的所有模型也会一并删除。
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
    </>
  )
}
