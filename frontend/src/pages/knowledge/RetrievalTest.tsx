import { useState } from 'react'
import { FileText, Search } from 'lucide-react'
import { ring } from 'ldrs'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { retrievalTest } from '@/api/knowledge'
import type { RetrievalHit } from '@/types'

ring.register()

interface RetrievalTestProps {
  kbId: string
}

/**
 * 检索测试 tab：输入 query → 命中片段列表 + 相似度 + 来源文档
 *
 * v0 mock：500ms 延迟 + 假命中。等后端片6 接入后改 runMockRetrieval → retrieveKnowledge API。
 */
export function RetrievalTest({ kbId }: RetrievalTestProps) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState('5')
  const [results, setResults] = useState<RetrievalHit[] | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSearch() {
    const q = query.trim()
    if (!q) return
    setLoading(true)
    try {
      const res = await retrievalTest(kbId, q, parseInt(topK, 10))
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
          <Button size="sm" disabled={!query.trim() || loading} onClick={handleSearch}>
            <Search className="size-4" />
            检索
          </Button>
        </div>
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
  results: RetrievalHit[] | null
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
  if (results.length === 0) {
    return (
      <div className="text-muted-foreground rounded-lg border border-dashed py-16 text-center text-sm">
        没有命中
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="text-muted-foreground text-xs">
        命中 {results.length} 条片段
      </div>
      {results.map((r, i) => (
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
