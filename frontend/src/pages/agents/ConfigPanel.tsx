import { useEffect, useMemo, useState } from 'react'
import { AxiosError } from 'axios'
import { Check, ChevronsUpDown, Info } from 'lucide-react'
import { toast } from 'sonner'

import { updateAgent, type AgentUpdatePayload } from '@/api/agent'
import { listKnowledgeBases } from '@/api/knowledge'
import { listMCPServers } from '@/api/mcp'
import { listAllModels } from '@/api/model'
import { listTools } from '@/api/tool'
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
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  ModelParamsFields,
  fromApiParams,
  toApiParams,
  type ModelParamsValue,
} from '@/components/ModelParamsFields'
import { cn } from '@/lib/utils'
import type {
  Agent,
  AgentConfig,
  AIModel,
  KnowledgeBase,
  MCPServer,
  Tool,
} from '@/types'
import { KindBadge } from './KindBadge'
import { mockTemplates } from './mock'

interface ConfigPanelProps {
  agent: Agent
  /** 保存成功后回传整新 agent，父级覆盖详情页 state */
  onSaved: (agent: Agent) => void
}

/** Form 内部形状：从 agent 摊平、保存时再打包回 config */
interface FormState {
  name: string
  description: string
  /** 摊平字段：编辑时方便、save 时打包成 config.models.chat.id */
  model_id: string | null
  system_prompt: string
  knowledge_ids: string[]
  tool_ids: string[]
  mcp_server_ids: string[]
  /** 旧版 mcp_ids 改名 —— 对齐后端 schema 的 skills 字段（mock 期 MCP = skill） */
  skill_ids: string[]
  /** 调用参数：save 时打包成 config.models.chat.params（maxTokens=null → 不发上限） */
  params: ModelParamsValue
}

function agentToForm(agent: Agent): FormState {
  const c = agent.config
  const chat = c.models?.chat
  return {
    name: agent.name,
    description: agent.description,
    model_id: chat?.id ?? null,
    system_prompt: c.system_prompt ?? '',
    knowledge_ids: c.knowledge ?? [],
    tool_ids: c.builtin_tools ?? [],
    mcp_server_ids: c.mcp_servers ?? [],
    skill_ids: c.skills ?? [],
    params: fromApiParams(chat?.params),
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
  const [chatModels, setChatModels] = useState<AIModel[]>([])
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [tools, setTools] = useState<Tool[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])

  // 切换 agent / 外部 setAgent 时（保存成功覆盖）同步本地 form
  useEffect(() => {
    setForm(agentToForm(agent))
  }, [agent])

  // 一次性拉资源池（chat 模型 + 知识库）
  useEffect(() => {
    listAllModels({ modelType: 'chat', enabledOnly: true })
      .then(setChatModels)
      .catch(() => {})
    listKnowledgeBases()
      .then(setKnowledgeBases)
      .catch(() => {})
    listTools()
      .then(setTools)
      .catch(() => {})
    listMCPServers()
      .then(setMcpServers)
      .catch(() => {})
  }, [])

  const dirty = useMemo(() => {
    const fresh = agentToForm(agent)
    return JSON.stringify(fresh) !== JSON.stringify(form)
  }, [agent, form])

  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function setToolSelection(names: string[]) {
    // 工具选择器只管内置工具，选中的 name 写进 config.builtin_tools。
    // MCP / custom 那天进来时，再按 source_type 分流到各自字段。
    const builtinNames = names.filter(
      (n) => tools.find((t) => t.name === n)?.source_type === 'builtin',
    )
    setForm((prev) => ({ ...prev, tool_ids: builtinNames }))
  }

  async function save() {
    const name = form.name.trim()
    if (!name) {
      toast.warning('名字不能为空')
      return
    }
    setSaving(true)
    // 显式构造嵌套 config（不 spread 旧 agent.config 防带入旧 schema 残留字段）
    const config: AgentConfig = {
      models: {
        chat: form.model_id
          ? { id: form.model_id, params: toApiParams(form.params) }
          : null,
      },
      system_prompt: form.system_prompt.trim() || null,
      capabilities: agent.config.capabilities ?? [],
      knowledge: form.knowledge_ids,
      builtin_tools: form.tool_ids,
      mcp_servers: form.mcp_server_ids,
      skills: form.skill_ids,
      behavior: agent.config.behavior ?? {},
      ui: agent.config.ui ?? {},
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
  const selectedToolIds = form.tool_ids
  const avatarUrl = agent.config.ui?.avatar_url ?? '/gopher-fcb-glass.png'

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
        <div className="space-y-6 px-1 py-5">
          {/* 身份 */}
          <Section label="身份">
            <div className="bg-muted/40 space-y-3 rounded-lg border p-4">
              <div className="flex items-center gap-3">
                <img
                  src={avatarUrl}
                  alt={form.name}
                  className="size-14 shrink-0 rounded-full object-cover"
                />
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <Input
                    value={form.name}
                    onChange={(e) => patch('name', e.target.value)}
                    placeholder="给 Agent 起个名字"
                    className="hover:bg-background h-9 rounded border-none px-2 text-base font-semibold shadow-none transition-colors focus-visible:ring-0 focus-visible:bg-background"
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
                className="text-muted-foreground hover:bg-background focus-visible:bg-background min-h-12 resize-none rounded border-none px-2 text-sm shadow-none transition-colors focus-visible:ring-0"
              />
            </div>
          </Section>

          {/* 行为 */}
          <Section label="行为">
            <div className="space-y-5">
              <Field label="模型" hint="必填——不配模型沙盒没法跑">
                <Select
                  value={form.model_id ?? undefined}
                  onValueChange={(v) => patch('model_id', v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="选择对话模型" />
                  </SelectTrigger>
                  <SelectContent>
                    {chatModels.length === 0 ? (
                      <div className="text-muted-foreground px-2 py-1.5 text-xs">
                        无可用的 chat 模型
                      </div>
                    ) : (
                      chatModels.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.display_name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </Field>

              <Accordion type="single" collapsible>
                <AccordionItem value="params" className="border-none">
                  <AccordionTrigger className="py-1 text-sm font-medium hover:no-underline">
                    调用参数
                  </AccordionTrigger>
                  <AccordionContent className="pt-3">
                    <ModelParamsFields
                      value={form.params}
                      onChange={(v) => patch('params', v)}
                    />
                  </AccordionContent>
                </AccordionItem>
              </Accordion>

              <Field label="System Prompt">
                <Textarea
                  value={form.system_prompt}
                  placeholder="留空 = 使用模板默认行为"
                  onChange={(e) => patch('system_prompt', e.target.value)}
                  className="min-h-32 resize-y font-mono text-xs leading-relaxed"
                />
              </Field>
            </div>
          </Section>

          {/* 资源 */}
          <Section label="资源">
            <div className="space-y-5">
              <Field label="知识库">
                <MultiSelectPopover
                  items={knowledgeBases.map((k) => ({ id: k.id, name: k.name }))}
                  value={form.knowledge_ids}
                  onChange={(ids) => patch('knowledge_ids', ids)}
                  placeholder="搜索知识库..."
                  emptyLabel="未挂载任何知识库"
                />
              </Field>

              <Field label="内置工具">
                <MultiSelectPopover
                  items={tools.map((t) => ({
                    id: t.name,
                    name: t.display_name,
                  }))}
                  value={selectedToolIds}
                  onChange={setToolSelection}
                  placeholder="搜索内置工具..."
                  emptyLabel="未挂载任何内置工具"
                />
              </Field>

              <Field label="MCP server">
                <MultiSelectPopover
                  items={mcpServers.map((s) => ({
                    id: s.id,
                    name: s.name,
                    meta: 'MCP',
                  }))}
                  value={form.mcp_server_ids}
                  onChange={(ids) => patch('mcp_server_ids', ids)}
                  placeholder="搜索 MCP server..."
                  emptyLabel="未挂载任何 MCP server"
                />
              </Field>
            </div>
          </Section>

          <p className="text-muted-foreground/60 pt-4 text-center text-[10px]">
            点击右上「保存」提交本次改动
          </p>
        </div>
      </div>
    </div>
  )
}

/** 语义分组小标题：身份 / 行为 / 资源 */
function Section({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2 px-1">
        <span className="bg-brand h-4 w-1 rounded-full" />
        <span className="text-foreground text-sm font-semibold">{label}</span>
      </div>
      {children}
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
    <div className="space-y-2">
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
