import { useEffect, useMemo, useState } from 'react'
import { AxiosError } from 'axios'
import { Check, ChevronsUpDown, Info } from 'lucide-react'
import { toast } from 'sonner'

import { updateAgent, type AgentUpdatePayload } from '@/api/agent'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { Agent, AgentConfig } from '@/types'
import { KindBadge } from './KindBadge'
import { mockChatModels, mockKnowledge, mockTemplates, mockTools } from './mock'

interface ConfigPanelProps {
  agent: Agent
  /** 保存成功后回传整新 agent，父级覆盖详情页 state */
  onSaved: (agent: Agent) => void
}

/** Form 内部形状：从 agent 摊平、保存时再打包回 config */
interface FormState {
  name: string
  description: string
  model_id: string | null
  system_prompt: string
  knowledge_ids: string[]
  tool_ids: string[]
  mcp_ids: string[]
  avatar_color: string
  temperature: number
  top_p: number
  max_tokens: number
}

function agentToForm(agent: Agent): FormState {
  const c = agent.config
  return {
    name: agent.name,
    description: agent.description,
    model_id: c.model_id ?? null,
    system_prompt: c.system_prompt ?? '',
    knowledge_ids: c.knowledge_ids ?? [],
    tool_ids: c.tool_ids ?? [],
    mcp_ids: c.mcp_ids ?? [],
    avatar_color: c.avatar_color ?? '#2f6b53',
    temperature: c.params?.temperature ?? 1,
    top_p: c.params?.top_p ?? 1,
    max_tokens: c.params?.max_tokens ?? 1024,
  }
}

/**
 * Agent 左栏配置。
 *
 * **保存模式**：表单态全部走本地 state；右上「保存」按钮触发整体 PUT
 * （`AgentUpdatePayload` 把摊平字段打包回 `config`）。脏态显示橙点提示。
 */
export function ConfigPanel({ agent, onSaved }: ConfigPanelProps) {
  const [form, setForm] = useState<FormState>(() => agentToForm(agent))
  const [saving, setSaving] = useState(false)

  // 切换 agent / 外部 setAgent 时（保存成功覆盖）同步本地 form
  useEffect(() => {
    setForm(agentToForm(agent))
  }, [agent])

  const dirty = useMemo(() => {
    const fresh = agentToForm(agent)
    return JSON.stringify(fresh) !== JSON.stringify(form)
  }, [agent, form])

  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function setToolSelection(ids: string[]) {
    // mock 的 ToolMock 区分 builtin / mcp，按 type 落到对应字段
    const tool_ids = ids.filter(
      (id) => mockTools.find((t) => t.id === id)?.type === 'builtin',
    )
    const mcp_ids = ids.filter(
      (id) => mockTools.find((t) => t.id === id)?.type === 'mcp',
    )
    setForm((prev) => ({ ...prev, tool_ids, mcp_ids }))
  }

  async function save() {
    const name = form.name.trim()
    if (!name) {
      toast.warning('名字不能为空')
      return
    }
    setSaving(true)
    const config: AgentConfig = {
      ...agent.config,
      model_id: form.model_id,
      system_prompt: form.system_prompt.trim() || null,
      knowledge_ids: form.knowledge_ids,
      tool_ids: form.tool_ids,
      mcp_ids: form.mcp_ids,
      avatar_color: form.avatar_color,
      params: {
        temperature: form.temperature,
        top_p: form.top_p,
        max_tokens: form.max_tokens,
      },
    }
    const payload: AgentUpdatePayload = {
      name,
      description: form.description,
      config,
    }
    try {
      const updated = await updateAgent(agent.id, payload)
      onSaved(updated)
      toast.success('已保存')
    } catch (err) {
      const msg =
        err instanceof AxiosError ? err.response?.data?.message : null
      toast.error(typeof msg === 'string' ? msg : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // 模板元数据反查（kind badge 展示）
  const template = mockTemplates.find((t) => t.key === agent.template)
  const templateKind = template?.kind ?? 'loop'
  const selectedToolIds = [...form.tool_ids, ...form.mcp_ids]

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Sticky 顶栏：dirty + 保存 */}
      <div className="flex shrink-0 items-center justify-between gap-2 border-b px-1 pb-2">
        <div className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
          {dirty ? (
            <>
              <span className="bg-warning size-1.5 rounded-full" />
              <span>有未保存改动</span>
            </>
          ) : (
            <span>已同步</span>
          )}
        </div>
        <Button size="sm" disabled={!dirty || saving} onClick={save}>
          {saving ? '保存中…' : '保存'}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-1 py-3">
          {/* Header：头像 + 名字 + kind badge + 描述 */}
          <div className="space-y-3 pb-5">
            <div className="flex items-center gap-3">
              <div
                className="flex size-14 shrink-0 items-center justify-center rounded-full text-lg font-medium text-white"
                style={{ backgroundColor: form.avatar_color }}
              >
                {form.name.slice(0, 1) || '?'}
              </div>
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <Input
                  value={form.name}
                  onChange={(e) => patch('name', e.target.value)}
                  className="h-9 border-none px-0 text-base font-semibold shadow-none focus-visible:ring-0"
                />
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="shrink-0">
                      <KindBadge kind={templateKind} className="cursor-help" />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>模板创建时选定，不可更改</TooltipContent>
                </Tooltip>
              </div>
            </div>
            <Textarea
              value={form.description}
              placeholder="一句话告诉别人这个 Agent 擅长什么"
              onChange={(e) => patch('description', e.target.value)}
              className="text-muted-foreground min-h-12 resize-none border-none px-0 text-sm shadow-none focus-visible:ring-0"
            />
          </div>

          <Separator />

          {/* 模型 */}
          <Field label="模型" hint="必填——不配模型沙盒没法跑">
            <Select
              value={form.model_id ?? undefined}
              onValueChange={(v) => patch('model_id', v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择对话模型" />
              </SelectTrigger>
              <SelectContent>
                {mockChatModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Separator />

          {/* 调用参数（默认折叠） */}
          <Accordion type="single" collapsible className="py-2">
            <AccordionItem value="params" className="border-none">
              <AccordionTrigger className="py-1 text-sm font-medium hover:no-underline">
                调用参数
              </AccordionTrigger>
              <AccordionContent className="space-y-5 pt-3">
                <SliderField
                  label="temperature"
                  value={form.temperature}
                  min={0}
                  max={2}
                  step={0.1}
                  onChange={(v) => patch('temperature', v)}
                />
                <SliderField
                  label="top_p"
                  value={form.top_p}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={(v) => patch('top_p', v)}
                />
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-xs">max_tokens</Label>
                  <Input
                    type="number"
                    value={form.max_tokens}
                    onChange={(e) =>
                      patch('max_tokens', Number(e.target.value) || 0)
                    }
                    className="h-8"
                  />
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          <Separator />

          {/* System Prompt */}
          <Field label="System Prompt">
            <Textarea
              value={form.system_prompt}
              placeholder="留空 = 使用模板默认行为"
              onChange={(e) => patch('system_prompt', e.target.value)}
              className="min-h-32 resize-y font-mono text-xs leading-relaxed"
            />
          </Field>

          <Separator />

          {/* 知识库 */}
          <Field label="知识库">
            <MultiSelectPopover
              items={mockKnowledge.map((k) => ({ id: k.id, name: k.name }))}
              value={form.knowledge_ids}
              onChange={(ids) => patch('knowledge_ids', ids)}
              placeholder="搜索知识库..."
              emptyLabel="未挂载任何知识库"
            />
          </Field>

          <Separator />

          {/* 工具 / MCP */}
          <Field label="工具 / MCP">
            <MultiSelectPopover
              items={mockTools.map((t) => ({
                id: t.id,
                name: t.name,
                meta: t.type === 'mcp' ? 'MCP' : '内置',
              }))}
              value={selectedToolIds}
              onChange={setToolSelection}
              placeholder="搜索工具..."
              emptyLabel="未挂载任何工具"
            />
          </Field>

          <p className="text-muted-foreground/60 pt-6 text-center text-[10px]">
            点击右上「保存」提交本次改动
          </p>
        </div>
      </div>
    </div>
  )
}

/** 通用字段壳：上下统一留呼吸空间，label 弱化 */
function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-2 py-4">
      <div className="flex items-center gap-1.5">
        <Label className="text-sm font-medium">{label}</Label>
        {hint && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="text-muted-foreground/60 size-3 cursor-help" />
            </TooltipTrigger>
            <TooltipContent>{hint}</TooltipContent>
          </Tooltip>
        )}
      </div>
      {children}
    </div>
  )
}

/** Slider + 当前值显示，拖动随动即落 form（保存按钮才提交后端） */
function SliderField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{label}</Label>
        <span className="text-muted-foreground font-mono text-xs tabular-nums">
          {value.toFixed(step < 0.1 ? 2 : 1)}
        </span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(v[0])}
      />
    </div>
  )
}

interface MultiItem {
  id: string
  name: string
  meta?: string
}

function MultiSelectPopover({
  items,
  value,
  onChange,
  placeholder,
  emptyLabel,
}: {
  items: MultiItem[]
  value: string[]
  onChange: (ids: string[]) => void
  placeholder: string
  emptyLabel: string
}) {
  const [open, setOpen] = useState(false)
  const selectedItems = items.filter((i) => value.includes(i.id))

  function toggle(id: string) {
    onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id])
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="h-auto min-h-9 w-full justify-between">
          <div className="flex flex-wrap items-center gap-1">
            {selectedItems.length === 0 ? (
              <span className="text-muted-foreground text-sm font-normal">{emptyLabel}</span>
            ) : (
              selectedItems.map((i) => (
                <Badge key={i.id} variant="secondary" className="text-xs">
                  {i.name}
                </Badge>
              ))
            )}
          </div>
          <ChevronsUpDown className="size-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-(--radix-popover-trigger-width) p-0">
        <Command>
          <CommandInput placeholder={placeholder} className="h-9" />
          <CommandList>
            <CommandEmpty>没有匹配项</CommandEmpty>
            <CommandGroup>
              {items.map((i) => {
                const checked = value.includes(i.id)
                return (
                  <CommandItem key={i.id} onSelect={() => toggle(i.id)}>
                    <Check className={cn('size-4', checked ? 'opacity-100' : 'opacity-0')} />
                    <span className="flex-1">{i.name}</span>
                    {i.meta && (
                      <Badge variant="outline" className="ml-2 text-[10px]">
                        {i.meta}
                      </Badge>
                    )}
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
