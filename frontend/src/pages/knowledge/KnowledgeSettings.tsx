import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Lock, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { listAllModels } from '@/api/model'
import { deleteKnowledgeBase, getParseBackends, updateKnowledgeBase } from '@/api/knowledge'
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
import { RETRIEVAL_MODE_LABEL } from '@/lib/retrieval'
import { useWorkspaceTabsStore } from '@/stores/tab-store'
import {
  ALL_PARSE_BACKENDS,
  PARSE_BACKEND_HINTS,
  PARSE_BACKEND_LABELS,
  type AIModel,
  type KnowledgeBase,
  type ParseBackend,
  type RetrievalMode,
} from '@/types'

/** Radix Select 的 value 不允许空字符串，用哨兵值表示「不配精排模型」 */
const SENTINEL_NONE = '__none__'

interface KnowledgeSettingsProps {
  kb: KnowledgeBase
  /** 保存成功后回传最新 kb，让详情页 header 同步刷新 */
  onUpdated?: (kb: KnowledgeBase) => void
}

/** 设置 tab —— 四分区：基本信息 / 检索设置 / 向量化配置(只读) / 危险操作 */
export function KnowledgeSettings({ kb, onUpdated }: KnowledgeSettingsProps) {
  const navigate = useNavigate()
  const [name, setName] = useState(kb.name)
  const [description, setDescription] = useState(kb.description)
  const [saving, setSaving] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // 检索设置
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>(kb.retrieval_mode)
  const [rerankModelId, setRerankModelId] = useState<string>(kb.rerank_model_id ?? SENTINEL_NONE)
  const [rerankModels, setRerankModels] = useState<AIModel[]>([])
  const [rerankModelsLoading, setRerankModelsLoading] = useState(false)
  const [retrievalSaving, setRetrievalSaving] = useState(false)

  const retrievalDirty =
    retrievalMode !== kb.retrieval_mode ||
    (rerankModelId === SENTINEL_NONE ? kb.rerank_model_id !== null : rerankModelId !== kb.rerank_model_id)

  // 解析设置
  const [parseBackend, setParseBackend] = useState<ParseBackend>(kb.parse_backend)
  // 初值取当前库在用的那个：它既然已经生效，至少它是可选的。等接口回来再覆盖
  const [availableBackends, setAvailableBackends] = useState<ParseBackend[]>([
    kb.parse_backend,
  ])
  const [parseSaving, setParseSaving] = useState(false)

  const parseDirty = parseBackend !== kb.parse_backend

  // 加载精排模型列表
  useEffect(() => {
    setRerankModelsLoading(true)
    listAllModels({ modelType: 'rerank', enabledOnly: true })
      .then(setRerankModels)
      .catch(() => {})
      .finally(() => setRerankModelsLoading(false))
  }, [])

  // 可选解析后端取决于部署侧配没配 Key，前端看不见，只能问后端
  useEffect(() => {
    getParseBackends().then(setAvailableBackends).catch(() => {})
  }, [])

  const dirty =
    name.trim() !== kb.name || description.trim() !== kb.description
  const canSave = dirty && name.trim() && !saving

  async function handleSave() {
    if (!canSave) return
    setSaving(true)
    try {
      const updated = await updateKnowledgeBase(kb.id, {
        name: name.trim(),
        description: description.trim(),
      })
      toast.success('设置已保存')
      onUpdated?.(updated)
    } catch (e) {
      // update 走 silent，失败自行 toast
      toast.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  function handleReset() {
    setName(kb.name)
    setDescription(kb.description)
  }

  async function handleRetrievalSave() {
    setRetrievalSaving(true)
    try {
      const updated = await updateKnowledgeBase(kb.id, {
        retrieval_mode: retrievalMode,
        rerank_model_id: rerankModelId === SENTINEL_NONE ? null : rerankModelId,
      })
      toast.success('检索设置已保存')
      onUpdated?.(updated)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '保存检索设置失败')
    } finally {
      setRetrievalSaving(false)
    }
  }

  async function handleParseSave() {
    setParseSaving(true)
    try {
      const updated = await updateKnowledgeBase(kb.id, { parse_backend: parseBackend })
      toast.success('解析设置已保存')
      onUpdated?.(updated)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '保存解析设置失败')
    } finally {
      setParseSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteKnowledgeBase(kb.id)
      toast.success(`知识库「${kb.name}」已删除`)
      // 关掉本库详情标签（删完跳回列表，否则残留死链标签）
      useWorkspaceTabsStore.getState().close(`/knowledge/${kb.id}`)
      navigate({ to: '/knowledge' })
    } catch {
      // 删除非 silent，失败拦截器已 toast
    } finally {
      setDeleting(false)
      setConfirmOpen(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* 分区1 · 基本信息 */}
      <Section title="基本信息" desc="知识库的名称与描述，随时可改">
        <div className="grid gap-2">
          <Label htmlFor="settings-name">
            名称 <span className="text-destructive">*</span>
          </Label>
          <Input
            id="settings-name"
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="settings-description">描述</Label>
          <Textarea
            id="settings-description"
            rows={2}
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            disabled={!dirty || saving}
          >
            撤销
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!canSave}>
            {saving ? '保存中…' : '保存修改'}
          </Button>
        </div>
      </Section>

      {/* 分区2 · 检索设置 */}
      <Section
        title="检索设置"
        desc="agent 调用本知识库（KB-as-tool）时使用的检索配置；命中测试面板可临时换模式试，不影响这里。"
      >
        <div className="grid gap-2">
          <Label className="text-xs">检索模式</Label>
          <Select value={retrievalMode} onValueChange={(v) => setRetrievalMode(v as RetrievalMode)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(RETRIEVAL_MODE_LABEL).map(([k, label]) => (
                <SelectItem key={k} value={k}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-muted-foreground text-xs">
            向量检索按语义找、关键词检索按词面找、混合检索两路并发后融合排名。
            词面精确查询（编号 / 型号 / 专有名词）多的库才值得开混合。
          </p>
        </div>
        <div className="grid gap-2">
          <Label className="text-xs">精排模型</Label>
          <Select
            value={rerankModelId}
            onValueChange={setRerankModelId}
            disabled={rerankModelsLoading}
          >
            <SelectTrigger className="w-full">
              <SelectValue
                placeholder={rerankModelsLoading ? '加载中…' : '选择精排模型'}
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SENTINEL_NONE}>关闭（单级检索）</SelectItem>
              {rerankModels.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  <span>{m.display_name}</span>
                  <span className="text-muted-foreground ml-2 font-mono text-xs">
                    {m.model_name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-muted-foreground text-xs">
            配了就启用：先放大候选窗口粗排，再由精排模型逐条重打分、截断返回。
            排序更准，代价是每次检索多一次模型调用。
          </p>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button
            size="sm"
            onClick={handleRetrievalSave}
            disabled={!retrievalDirty || retrievalSaving}
          >
            {retrievalSaving ? '保存中…' : '保存检索设置'}
          </Button>
        </div>
      </Section>

      {/* 分区3 · 解析设置 */}
      <Section
        title="解析设置"
        desc="决定 PDF 走哪条路解析。改了只影响此后新传的文档——存量文档要重新处理才按新设置生效。"
      >
        <div className="grid gap-2">
          <Label className="text-xs">PDF 解析方式</Label>
          <Select
            value={parseBackend}
            onValueChange={(v) => setParseBackend(v as ParseBackend)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ALL_PARSE_BACKENDS.map((backend) => {
                const usable = availableBackends.includes(backend)
                return (
                  <SelectItem key={backend} value={backend} disabled={!usable}>
                    <span>{PARSE_BACKEND_LABELS[backend]}</span>
                    {!usable && (
                      <span className="text-muted-foreground ml-2 text-xs">
                        未配置凭证
                      </span>
                    )}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
          <p className="text-muted-foreground text-xs">
            {PARSE_BACKEND_HINTS[parseBackend]}
          </p>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button
            size="sm"
            onClick={handleParseSave}
            disabled={!parseDirty || parseSaving}
          >
            {parseSaving ? '保存中…' : '保存解析设置'}
          </Button>
        </div>
      </Section>

      {/* 分区4 · 向量化配置（只读锁定） */}
      <Section
        title="向量化配置"
        desc="建库后锁定。更换 embedding 模型或切块参数需重新向量化全部文档（后续支持）。"
        icon={<Lock className="text-muted-foreground size-4" />}
      >
        <ReadonlyField
          label="Embedding 模型"
          value={`${kb.embedding_model_name} · ${kb.embedding_dim} 维`}
        />
        <div className="grid grid-cols-2 gap-4">
          <ReadonlyField label="Chunk Size" value={`${kb.chunk_config.chunk_size} token`} />
          <ReadonlyField label="Overlap" value={`${kb.chunk_config.overlap} token`} />
        </div>
        <ReadonlyField label="切分策略" value="递归切分" />
      </Section>

      {/* 分区5 · 危险操作 */}
      <Section
        title="危险操作"
        tone="destructive"
        desc="删除后知识库本身与下属文档、向量数据将一并清除，且不可恢复。"
      >
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            className="border-destructive/40 text-destructive hover:bg-destructive/5 hover:text-destructive"
            onClick={() => setConfirmOpen(true)}
          >
            <Trash2 className="size-4" />
            删除知识库
          </Button>
        </div>
      </Section>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除知识库「{kb.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              该操作不可撤销。库下的 {kb.doc_count} 篇文档与 {kb.chunk_count.toLocaleString()} 条向量将一并清除。
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
              {deleting ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ---------- 内部小组件 ----------

function Section({
  title,
  desc,
  icon,
  tone = 'default',
  children,
}: {
  title: string
  desc?: string
  icon?: React.ReactNode
  tone?: 'default' | 'destructive'
  children: React.ReactNode
}) {
  const isDestructive = tone === 'destructive'
  return (
    <section
      className={
        isDestructive
          ? 'border-destructive/30 rounded-lg border bg-destructive/[0.02] p-5 space-y-4'
          : 'rounded-lg border p-5 space-y-4'
      }
    >
      <div>
        <div className="flex items-center gap-2">
          <h3
            className={
              isDestructive
                ? 'text-destructive text-sm font-semibold'
                : 'text-sm font-semibold'
            }
          >
            {title}
          </h3>
          {icon}
        </div>
        {desc && <p className="text-muted-foreground mt-1 text-xs">{desc}</p>}
      </div>
      {children}
    </section>
  )
}

function ReadonlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-muted-foreground text-xs font-normal">
        {label}
      </Label>
      <div className="bg-muted/40 text-foreground rounded-md border px-3 py-2 text-sm">
        {value}
      </div>
    </div>
  )
}
