import { useState } from 'react'
import { FileText, Layers, Search, Timer } from 'lucide-react'
import { ring } from 'ldrs'

import { retrievalTest } from '@/api/knowledge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { RETRIEVAL_MODE_LABEL } from '@/lib/retrieval'
import type { RetrievalMode, RetrievalTestResult } from '@/types'

ring.register()

interface RetrievalTestProps {
  kbId: string
  /** 本库设置里配的检索模式，作为面板的初值 */
  kbMode: RetrievalMode
  /** 本库配置的精排模型；null = 没配，精排开关不可用 */
  rerankModelId: string | null
  rerankModelName: string | null
}

/**
 * 检索测试 tab = 实验台：输入 query → 命中片段 + 相似度 + 来源 + 分段耗时，不落库。
 *
 * 两个旋钮的形态刻意不同，判据是「枚举参数就地试，资源引用只在一处绑」：
 * - **检索模式**是枚举参数，面板上直接换（**仅本次生效、不改库设置**），
 *   实验台不能就地换参数就没有存在价值；
 * - **精排模型**是资源引用，只在设置页绑定，这里只给开关——两处都能选具体模型
 *   会让「我改了到底存没存」变得含糊。关 = 不化妆的原始召回（索引体检，默认）；
 *   开 = 用库上配好的模型，预览 agent 实际会拿到什么。
 */
export function RetrievalTest({
  kbId,
  kbMode,
  rerankModelId,
  rerankModelName,
}: RetrievalTestProps) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState('5')
  const [results, setResults] = useState<RetrievalTestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<RetrievalMode>(kbMode)
  const [rerankOn, setRerankOn] = useState(false)

  const rerankAvailable = rerankModelId !== null

  async function handleSearch() {
    const q = query.trim()
    if (!q) return
    setLoading(true)
    try {
      const res = await retrievalTest(kbId, {
        query: q,
        topK: parseInt(topK, 10),
        mode,
        rerankModelId: rerankOn && rerankAvailable ? rerankModelId : undefined,
      })
      setResults(res)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Cmd/Ctrl+Enter 触发检索（query 多行用 Enter 换行更自然）
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  return (
    <div className="space-y-4">
      {/* 查询输入区 */}
      <div className="bg-card space-y-3 rounded-lg border p-4 shadow-sm">
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入查询，例如：怎么集成 API？（Cmd/Ctrl+Enter 检索）"
          className="min-h-20 resize-none text-sm"
        />
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs">模式</span>
              <Select value={mode} onValueChange={(v) => setMode(v as RetrievalMode)}>
                <SelectTrigger className="h-8 w-32">
                  {/* 显式给 children：否则 Radix 会把选中项的全部内容（含「· 库默认」标记）搬进触发器 */}
                  <SelectValue>{RETRIEVAL_MODE_LABEL[mode]}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(RETRIEVAL_MODE_LABEL).map(([k, label]) => (
                    <SelectItem key={k} value={k}>
                      {label}
                      {k === kbMode && (
                        <span className="text-muted-foreground ml-1 text-xs">· 库默认</span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs">topK</span>
              <Select value={topK} onValueChange={setTopK}>
                <SelectTrigger className="h-8 w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {['3', '5', '10', '20'].map((n) => (
                    <SelectItem key={n} value={n}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="retrieval-rerank"
                checked={rerankOn}
                onCheckedChange={setRerankOn}
                disabled={!rerankAvailable}
              />
              <Label
                htmlFor="retrieval-rerank"
                className="text-muted-foreground text-xs font-normal"
              >
                精排
              </Label>
            </div>
          </div>
          <Button size="sm" disabled={!query.trim() || loading} onClick={handleSearch}>
            <Search className="size-4" />
            检索
          </Button>
        </div>
        <p className="text-muted-foreground text-xs">
          面板上的模式仅本次检索生效，不会改动库设置 ·{' '}
          {rerankAvailable ? (
            <>
              精排模型：{rerankModelName}
              {rerankOn ? '（已开启，预览 agent 实际拿到的结果）' : '（关闭中，看不化妆的原始召回）'}
            </>
          ) : (
            <>本库未配置精排模型，可在「设置」tab 配置后开启</>
          )}
        </p>
      </div>

      {/* 结果区 */}
      <ResultsArea loading={loading} results={results} />
    </div>
  )
}

function ResultsArea({
  loading,
  results,
}: {
  loading: boolean
  results: RetrievalTestResult | null
}) {
  if (loading) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <l-ring size="32" stroke="3" speed="2" color="#2f6b53" />
      </div>
    )
  }
  if (results === null) {
    return (
      <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-center">
        <Search className="size-8 opacity-40" />
        <p className="text-foreground text-sm font-medium">输入查询试一下检索效果</p>
        <p className="max-w-xs text-xs">
          命中片段、相似度、来源文档将展示在这里，方便你调试 prompt 与切块策略
        </p>
      </div>
    )
  }
  if (results.hits.length === 0) {
    return (
      <div className="text-muted-foreground rounded-lg border border-dashed py-16 text-center text-sm">
        没有命中 · 耗时 {results.total_ms}ms
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* 命中数 / 耗时两枚独立气泡，同排靠左 */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="bg-muted flex items-center gap-1.5 rounded-md px-2.5 py-1">
          <Layers className="text-muted-foreground size-4" />
          <span className="font-mono text-sm font-semibold">{results.hits.length}</span>
          <span className="text-muted-foreground text-xs">条命中</span>
        </div>
        <div className="bg-brand-subtle text-brand flex items-center gap-1.5 rounded-md px-2.5 py-1">
          <Timer className="size-4" />
          <span className="font-mono text-sm font-semibold">{results.total_ms} ms</span>
          <span className="font-mono text-xs opacity-80">
            · 向量化 {results.embed_ms} · 检索 {results.search_ms}
            {results.rerank_ms > 0 ? ` · 精排 ${results.rerank_ms}` : ''}
          </span>
        </div>
      </div>
      {results.hits.map((r, i) => (
        <div key={r.paragraph_id} className="bg-card space-y-2 rounded-lg border p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span className="text-muted-foreground font-mono text-xs">#{i + 1}</span>
              <FileText className="text-muted-foreground size-3.5 shrink-0" />
              <span className="truncate text-sm font-medium">{r.doc_name}</span>
            </div>
            <Badge variant="secondary" className="shrink-0 font-mono">
              {r.score.toFixed(3)}
            </Badge>
          </div>
          <p className="text-foreground text-sm leading-relaxed">{r.content}</p>
        </div>
      ))}
    </div>
  )
}
