import { useState } from 'react'
import { Check, ChevronsUpDown, Info } from 'lucide-react'

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
import { useAgentMockStore } from './agent-mock-store'
import { mockChatModels, mockKnowledge, mockTools } from './mock'

interface ConfigPanelProps {
  agent: Agent
}

/** Agent 左栏配置——所有改动即时落 store，无保存按钮 */
export function ConfigPanel({ agent }: ConfigPanelProps) {
  const update = useAgentMockStore((s) => s.update)

  // 名字 / 描述 用本地受控 state，失焦再 sync 到 store（避免每个字符都触发 update + 引发列表卡片闪烁）
  const [name, setName] = useState(agent.name)
  const [description, setDescription] = useState(agent.description)
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt ?? '')

  function commitField<K extends keyof Agent>(key: K, value: Agent[K]) {
    update(agent.id, { [key]: value } as Partial<Agent>)
  }

  function setModel(modelId: string) {
    const model = mockChatModels.find((m) => m.id === modelId)
    update(agent.id, {
      model_id: model?.id ?? null,
      model_display_name: model?.display_name ?? null,
    })
  }

  function setConfig(patch: Partial<AgentConfig>) {
    update(agent.id, { config: { ...agent.config, ...patch } })
  }

  function setKnowledgeIds(ids: string[]) {
    update(agent.id, { knowledge_ids: ids })
  }

  function setToolSelection(ids: string[]) {
    // mock 的 ToolMock 区分 builtin / mcp，按 type 落到对应字段
    const tool_ids = ids.filter((id) => mockTools.find((t) => t.id === id)?.type === 'builtin')
    const mcp_ids = ids.filter((id) => mockTools.find((t) => t.id === id)?.type === 'mcp')
    update(agent.id, { tool_ids, mcp_ids })
  }

  const temperature = agent.config.temperature ?? 1
  const topP = agent.config.top_p ?? 1
  const maxTokens = agent.config.max_tokens ?? 1024
  const selectedToolIds = [...agent.tool_ids, ...agent.mcp_ids]

  return (
    <div className="h-full overflow-y-auto">
      <div className="px-1 py-1">
        {/* Header：头像 + 名字 + behavior badge + 描述（一个 block，作为视觉焦点） */}
        <div className="space-y-3 pb-5">
          <div className="flex items-center gap-3">
            <div
              className="flex size-14 shrink-0 items-center justify-center rounded-full text-lg font-medium text-white"
              style={{ backgroundColor: agent.avatar_color }}
            >
              {agent.name.slice(0, 1)}
            </div>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => {
                  const trimmed = name.trim()
                  if (trimmed && trimmed !== agent.name) commitField('name', trimmed)
                  else setName(agent.name)
                }}
                className="h-9 border-none px-0 text-base font-semibold shadow-none focus-visible:ring-0"
              />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="secondary" className="cursor-help shrink-0">
                    {agent.behavior_type}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>行为模板创建时选定，不可更改</TooltipContent>
              </Tooltip>
            </div>
          </div>
          <Textarea
            value={description}
            placeholder="一句话告诉别人这个 Agent 擅长什么"
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => {
              if (description !== agent.description) commitField('description', description)
            }}
            className="text-muted-foreground min-h-12 resize-none border-none px-0 text-sm shadow-none focus-visible:ring-0"
          />
        </div>

        <Separator />

        {/* 模型 */}
        <Field label="模型" hint="必填——不配模型没法调 LLM">
          <Select value={agent.model_id ?? undefined} onValueChange={setModel}>
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
                value={temperature}
                min={0}
                max={2}
                step={0.1}
                onCommit={(v) => setConfig({ temperature: v })}
              />
              <SliderField
                label="top_p"
                value={topP}
                min={0}
                max={1}
                step={0.05}
                onCommit={(v) => setConfig({ top_p: v })}
              />
              <div className="space-y-2">
                <Label className="text-muted-foreground text-xs">max_tokens</Label>
                <Input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setConfig({ max_tokens: Number(e.target.value) || 0 })}
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
            value={systemPrompt}
            placeholder="留空 = 使用模板默认行为"
            onChange={(e) => setSystemPrompt(e.target.value)}
            onBlur={() => {
              const next = systemPrompt.trim() || null
              if (next !== agent.system_prompt) commitField('system_prompt', next)
            }}
            className="min-h-32 resize-y font-mono text-xs leading-relaxed"
          />
        </Field>

        <Separator />

        {/* 知识库 */}
        <Field label="知识库">
          <MultiSelectPopover
            items={mockKnowledge.map((k) => ({ id: k.id, name: k.name }))}
            value={agent.knowledge_ids}
            onChange={setKnowledgeIds}
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
          配置变更即时生效
        </p>
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

/** Slider + 当前值显示，拖动停下才提交（避免高频 update） */
function SliderField({
  label,
  value,
  min,
  max,
  step,
  onCommit,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onCommit: (v: number) => void
}) {
  const [local, setLocal] = useState(value)
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{label}</Label>
        <span className="text-muted-foreground font-mono text-xs tabular-nums">
          {local.toFixed(step < 0.1 ? 2 : 1)}
        </span>
      </div>
      <Slider
        value={[local]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => setLocal(v[0])}
        onValueCommit={(v) => onCommit(v[0])}
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
