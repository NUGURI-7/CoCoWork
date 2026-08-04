import { useEffect, useMemo, useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { ring } from 'ldrs'
import { toast } from 'sonner'

import { listUsers, setUserStatus } from '@/api/auth'
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

ring.register()

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

/** /admin/users — 用户管理（列表 + 启用/停用，接后端 /users 两个管理员端点） */
export default function UsersPage() {
  const currentUser = useAuthStore((s) => s.user)
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  // 待确认停用的人。只有「停用」需要二次确认 —— 重新启用是无害操作，点了就生效
  const [confirmUser, setConfirmUser] = useState<User | null>(null)
  // 正在提交的行，用来禁掉那一行的开关，避免连点打出两个相反的请求
  const [pendingId, setPendingId] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    listUsers()
      .then((list) => {
        if (alive) setUsers(list)
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

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

  /** 真正发请求那一步。成功后拿后端返回的那份覆盖本地，不自己拼状态 */
  async function applyStatus(user: User, value: boolean) {
    setPendingId(user.id)
    try {
      const updated = await setUserStatus(user.id, value)
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      toast.success(
        value
          ? `已启用「${updated.nick_name || updated.username}」`
          : `已停用「${updated.nick_name || updated.username}」`,
      )
    } finally {
      setPendingId(null)
    }
  }

  function handleToggle(user: User, value: boolean) {
    // 停用要确认（对方会立刻被踢出登录态），启用直接生效
    if (!value) {
      setConfirmUser(user)
      return
    }
    void applyStatus(user, true)
  }

  function confirmDisable() {
    if (!confirmUser) return
    const target = confirmUser
    setConfirmUser(null)
    void applyStatus(target, false)
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
            <TooltipContent>用户自行注册，后台不代建</TooltipContent>
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
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <l-ring size="28" stroke="3" speed="2" color="#2f6b53" />
          </div>
        ) : filtered.length === 0 ? (
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
                  <TableHead className="w-24 text-right">启用</TableHead>
                  <TableHead className="w-32">创建时间</TableHead>
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
                      <TableCell className="text-right">
                        {isSelf ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span tabIndex={0} className="inline-flex">
                                <Switch checked={u.is_active} disabled />
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>不能停用自己</TooltipContent>
                          </Tooltip>
                        ) : (
                          <Switch
                            checked={u.is_active}
                            disabled={pendingId === u.id}
                            onCheckedChange={(v) => handleToggle(u, v)}
                          />
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {formatDate(u.created_at)}
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
              <AlertDialogTitle>停用这个账户？</AlertDialogTitle>
              <AlertDialogDescription>
                「{confirmUser?.nick_name || confirmUser?.username}」（
                {confirmUser?.email}）将立刻无法登录，已经登录的会话也会在下一次
                操作时被踢出。数据全部保留，随时可以再启用。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault()
                  confirmDisable()
                }}
                variant="destructive"
              >
                确认停用
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  )
}
