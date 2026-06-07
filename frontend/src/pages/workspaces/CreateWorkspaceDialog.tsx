import { useEffect, useState } from 'react'
import { v4 as uuidv4 } from 'uuid'

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
import { Textarea } from '@/components/ui/textarea'
import type { Workspace } from '@/types'

interface CreateWorkspaceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 创建后回调，父级负责 push 列表 + 跳详情 */
  onCreate: (workspace: Workspace) => void
}

export function CreateWorkspaceDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateWorkspaceDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    setName('')
    setDescription('')
  }, [open])

  const canCreate = name.trim().length > 0

  function handleCreate() {
    if (!name.trim()) return
    const now = new Date().toISOString()
    const newWorkspace: Workspace = {
      id: uuidv4(),
      name: name.trim(),
      description: description.trim(),
      // 新空间默认带一个管家
      members: [
        {
          id: uuidv4(),
          name: '管家',
          avatar_color: '#2f6b53',
          role: 'supervisor',
          source: 'template',
          source_name: '调度',
          behavior_type: 'supervisor',
        },
      ],
      // 新空间默认带一条空对话
      conversations: [
        {
          id: uuidv4(),
          title: '新对话',
          created_at: now,
          updated_at: now,
        },
      ],
      created_at: now,
      updated_at: now,
    }
    onCreate(newWorkspace)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>创建工作空间</DialogTitle>
          <DialogDescription>起个名字，之后在空间里招募 agent 协作</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="ws-name" className="text-xs font-medium tracking-wide uppercase">
              名字
            </Label>
            <Input
              id="ws-name"
              value={name}
              placeholder="如：博士论文项目"
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="ws-desc" className="text-xs font-medium tracking-wide uppercase">
              描述 <span className="text-muted-foreground normal-case">（选填）</span>
            </Label>
            <Textarea
              id="ws-desc"
              value={description}
              placeholder="这个空间用来做什么"
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-20 resize-none"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canCreate} onClick={handleCreate}>
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
