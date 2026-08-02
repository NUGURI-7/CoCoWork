import { memo, useState } from 'react'
import { CircleHelp, Check } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { AskAnswer, AskBlock as AskBlockType, AskField } from '@/types'

interface AskBlockProps {
  block: AskBlockType
  /** 提交答案 —— 由 MessageList 从 store 传下来（块自己不认识 store） */
  onAnswer?: (blockIndex: number, answer: AskAnswer) => void
}

type FieldValue = string | boolean | string[]

/** 字段的初始值 —— 优先用后端给的 default，没有就按类型给空值。 */
function initialValue(field: AskField): FieldValue {
  switch (field.type) {
    case 'text':
      return field.default ?? ''
    case 'select':
      return field.default ?? ''
    case 'multi_select':
      return field.default ?? []
    case 'boolean':
      return field.default
  }
}

/** 必填校验：文本要非空、单选要选中、多选至少一项；勾选框本身恒有值。 */
function isFilled(field: AskField, value: FieldValue): boolean {
  if (!field.required) return true
  if (field.type === 'multi_select') return Array.isArray(value) && value.length > 0
  if (field.type === 'boolean') return true
  return typeof value === 'string' && value.trim().length > 0
}

/** 已作答时展示成一行结果，多选用顿号连起来。 */
function displayValue(value: FieldValue): string {
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value
}

/**
 * 人工确认块 —— Agent 停下来问用户的那张表单。
 *
 * 两种形态：
 * - 未作答：渲染可交互表单，填完点提交
 * - 已作答：塌缩成只读的结果行，历史里能看到「当时问了什么、我答了什么」
 *
 * `allow_custom` 的选项列表末尾会多一个「其他」，选中后出现输入框 —— 真实产品
 * 里这是一个字段而不是两个，免得出现「既选了 A 又填了别的」这种没法解释的组合。
 */
export const AskBlock = memo(function AskBlock({ block, onAnswer }: AskBlockProps) {
  const { answer, submitting } = block

  // 缺字段一律兜成空，不让一条结构不全的历史块白掉整页 —— 同 parse_blocks
  // 「烂块跳过不炸」的口径。后端将来改 payload 结构时，老历史也走这条路
  const payload = block.payload ?? ({} as Partial<AskBlockType['payload']>)
  const fields = payload.fields ?? []
  const actions = payload.actions ?? []

  const [values, setValues] = useState<Record<string, FieldValue>>(() =>
    Object.fromEntries(fields.map((f) => [f.name, initialValue(f)])),
  )
  // 哪些字段选了「其他」—— 选中时该字段改用自由输入
  const [custom, setCustom] = useState<Record<string, boolean>>({})

  const asker = payload.asker_name || '助手'
  const answered = answer !== null

  const canSubmit =
    !submitting &&
    fields.every((f) => isFilled(f, values[f.name] ?? initialValue(f)))

  const submit = (actionId: string) => {
    if (submitting) return
    onAnswer?.(block.index, { action: actionId, values })
  }

  // ---------- 已作答：只读结果 ----------
  if (answered) {
    const cancelled = answer.action === 'cancel'
    return (
      <div className="border-border/60 bg-muted/30 my-2 rounded-lg border px-3 py-2 text-sm">
        <div className="text-muted-foreground flex items-center gap-1.5 text-xs">
          <Check size={13} />
          <span>{cancelled ? `已跳过 ${asker} 的提问` : `已回复 ${asker}`}</span>
        </div>
        {!cancelled && (
          // 上下两行而不是左右两列：模型写的 label 可能很长（一句完整的问话），
          // 横排会把答案挤出卡片外
          <div className="mt-1.5 space-y-1.5">
            {fields.map((f) => (
              <div key={f.name} className="min-w-0">
                <div className="text-muted-foreground text-xs break-words">
                  {f.label}
                </div>
                <div className="font-medium break-words">
                  {displayValue(answer.values[f.name] ?? '')}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ---------- 未作答：可交互表单 ----------
  return (
    <div className="border-primary/30 bg-primary/[0.03] my-2 rounded-lg border px-3.5 py-3">
      <div className="text-muted-foreground mb-2.5 flex items-center gap-1.5 text-xs">
        <CircleHelp size={13} />
        <span>
          <span className="font-medium">{asker}</span> 需要你确认
        </span>
      </div>

      <p className="mb-3 text-sm font-medium">{payload.question}</p>

      <div className="space-y-3">
        {fields.map((field) => {
          const value = values[field.name] ?? initialValue(field)
          const setValue = (v: FieldValue) =>
            setValues((prev) => ({ ...prev, [field.name]: v }))

          return (
            <div key={field.name} className="space-y-1.5">
              {/* 单个字段时标题已经是问题本身，标签会重复，故只在多字段时显示 */}
              {fields.length > 1 && (
                <Label className="text-xs font-normal">
                  {field.label}
                  {field.required && <span className="text-destructive ml-0.5">*</span>}
                </Label>
              )}

              {field.type === 'text' &&
                (field.multiline ? (
                  <Textarea
                    value={value as string}
                    onChange={(e) => setValue(e.target.value)}
                    disabled={submitting}
                    rows={3}
                    className="text-sm"
                  />
                ) : (
                  <Input
                    value={value as string}
                    onChange={(e) => setValue(e.target.value)}
                    disabled={submitting}
                    className="h-8 text-sm"
                  />
                ))}

              {field.type === 'select' && (
                <div className="flex flex-wrap gap-1.5">
                  {field.options.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      disabled={submitting}
                      onClick={() => {
                        setCustom((p) => ({ ...p, [field.name]: false }))
                        setValue(opt)
                      }}
                      className={cn(
                        'rounded-md border px-2.5 py-1 text-xs transition-colors',
                        value === opt && !custom[field.name]
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border hover:bg-accent',
                      )}
                    >
                      {opt}
                    </button>
                  ))}
                  {field.allow_custom && (
                    <button
                      type="button"
                      disabled={submitting}
                      onClick={() => {
                        setCustom((p) => ({ ...p, [field.name]: true }))
                        setValue('')
                      }}
                      className={cn(
                        'rounded-md border px-2.5 py-1 text-xs transition-colors',
                        custom[field.name]
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border hover:bg-accent',
                      )}
                    >
                      其他
                    </button>
                  )}
                </div>
              )}

              {field.type === 'select' && custom[field.name] && (
                <Input
                  value={value as string}
                  onChange={(e) => setValue(e.target.value)}
                  disabled={submitting}
                  placeholder="说说你的想法"
                  className="h-8 text-sm"
                  autoFocus
                />
              )}

              {field.type === 'multi_select' && (
                <div className="flex flex-wrap gap-1.5">
                  {field.options.map((opt) => {
                    const list = (value as string[]) ?? []
                    const on = list.includes(opt)
                    return (
                      <button
                        key={opt}
                        type="button"
                        disabled={submitting}
                        onClick={() =>
                          setValue(
                            on ? list.filter((x) => x !== opt) : [...list, opt],
                          )
                        }
                        className={cn(
                          'rounded-md border px-2.5 py-1 text-xs transition-colors',
                          on
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border hover:bg-accent',
                        )}
                      >
                        {opt}
                      </button>
                    )
                  })}
                </div>
              )}

              {field.type === 'boolean' && (
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={value as boolean}
                    onCheckedChange={(c) => setValue(c === true)}
                    disabled={submitting}
                  />
                  <span className="text-sm">{field.label}</span>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="mt-3.5 flex gap-2">
        {actions.map((action) => {
          // 「跳过」这类不填也能点；提交类要等必填项齐了
          const isCancel = action.id === 'cancel'
          return (
            <Button
              key={action.id}
              size="sm"
              variant={
                action.style === 'danger'
                  ? 'destructive'
                  : action.style === 'primary'
                    ? 'default'
                    : 'outline'
              }
              disabled={submitting || (!isCancel && !canSubmit)}
              onClick={() => submit(action.id)}
            >
              {action.label}
            </Button>
          )
        })}
      </div>
    </div>
  )
})
