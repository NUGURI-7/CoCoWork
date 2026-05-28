import { useMemo, useState } from 'react'
import { Plus, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { useAuthStore } from '@/stores/auth'
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
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { User } from '@/types'
import { mockUsers } from './users-mock'

type RoleFilter = 'all' | 'admin' | 'user'

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

function initials(u: User): string {
  const src = (u.nick_name || u.username || '?').trim()
  return src.slice(0, 1).toUpperCase()
}

/** /admin/users — 用户管理（mock，待后端 user 管理接口） */
export default function UsersPage() {
  const currentUser = useAuthStore((s) => s.user)
  const [users, setUsers] = useState<User[]>(mockUsers)
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  const [confirmUser, setConfirmUser] = useState<User | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return users.filter((u) => {
      if (roleFilter === 'admin' && !u.is_admin) return false
      if (roleFilter === 'user' && u.is_admin) return false
      if (!q) return true
      return (
        u.username.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.nick_name.toLowerCase().includes(q)
      )
    })
  }, [users, query, roleFilter])

  function toggleActive(id: string, value: boolean) {
    setUsers((prev) =>
      prev.map((u) => (u.id === id ? { ...u, is_active: value } : u)),
    )
  }

  function handleDelete() {
    if (!confirmUser) return
    setUsers((prev) => prev.filter((u) => u.id !== confirmUser.id))
    toast.success(`已删除用户「${confirmUser.username}」`)
    setConfirmUser(null)
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* ① Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold">用户管理</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              管理平台用户的角色、启用状态与访问权限
            </p>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0}>
                <Button size="sm" disabled>
                  <Plus className="size-4" />
                  新建用户
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>等后端用户管理接口</TooltipContent>
          </Tooltip>
        </div>

        {/* ② 工具条 */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="text-muted-foreground pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
            <Input
              placeholder="搜索用户名 / 邮箱 / 昵称"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={roleFilter} onValueChange={(v) => setRoleFilter(v as RoleFilter)}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部角色</SelectItem>
              <SelectItem value="admin">管理员</SelectItem>
              <SelectItem value="user">普通用户</SelectItem>
            </SelectContent>
          </Select>
          <div className="text-muted-foreground ml-auto text-xs">
            共 {filtered.length} 人
          </div>
        </div>

        {/* ③ 表格 */}
        {filtered.length === 0 ? (
          <div className="border-border/60 text-muted-foreground flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-sm">
            <p>没有匹配的用户</p>
            <p className="mt-1 text-xs">调整搜索条件试试</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用户</TableHead>
                  <TableHead>邮箱</TableHead>
                  <TableHead className="w-28">角色</TableHead>
                  <TableHead className="w-24">状态</TableHead>
                  <TableHead className="w-32">创建时间</TableHead>
                  <TableHead className="w-16 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((u) => {
                  const isSelf = currentUser?.id === u.id
                  return (
                    <TableRow key={u.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="size-8">
                            <AvatarFallback className="bg-brand-subtle text-brand text-xs">
                              {initials(u)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium">
                              {u.nick_name || u.username}
                              {isSelf && (
                                <span className="text-muted-foreground ml-1.5 text-xs">
                                  （你）
                                </span>
                              )}
                            </div>
                            <div className="text-muted-foreground truncate font-mono text-xs">
                              {u.username}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {u.email}
                      </TableCell>
                      <TableCell>
                        {u.is_admin ? (
                          <Badge className="bg-brand-subtle text-brand border-brand-border hover:bg-brand-subtle">
                            管理员
                          </Badge>
                        ) : (
                          <Badge variant="secondary">普通</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {isSelf ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span tabIndex={0} className="inline-flex">
                                <Switch checked={u.is_active} disabled />
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>不能禁用自己</TooltipContent>
                          </Tooltip>
                        ) : (
                          <Switch
                            checked={u.is_active}
                            onCheckedChange={(v) => toggleActive(u.id, v)}
                          />
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {formatDate(u.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        {isSelf ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span tabIndex={0} className="inline-flex">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="text-muted-foreground size-7"
                                  disabled
                                >
                                  <Trash2 className="size-4" />
                                </Button>
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>不能删除自己</TooltipContent>
                          </Tooltip>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-muted-foreground hover:text-destructive size-7"
                            onClick={() => setConfirmUser(u)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}

        <AlertDialog
          open={confirmUser !== null}
          onOpenChange={(v) => !v && setConfirmUser(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>删除用户？</AlertDialogTitle>
              <AlertDialogDescription>
                将删除「{confirmUser?.nick_name || confirmUser?.username}」（
                {confirmUser?.email}）及其所有数据，此操作不可恢复。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault()
                  handleDelete()
                }}
                className="bg-destructive hover:bg-destructive/90 text-white"
              >
                确认删除
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  )
}
