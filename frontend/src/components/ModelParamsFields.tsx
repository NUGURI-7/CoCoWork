import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import type { ModelParams } from '@/types'

/**
 * 模型调用参数编辑器 —— Agent ConfigPanel / Workspace 管家配置共用。
 *
 * temperature 常驻滑杆（默认 1 == 多数 provider 默认，无害恒发）。
 * max_tokens 走开关门控：关 = 不限制、不发参数（模型用自然上限）；开 = 出滑杆、发 max_tokens。
 * 「不发 = 不截断」是默认，避免给所有对话硬塞一个输出上限。
 * reasoning_effort 只在模型支持时出现（levels 由后端按 model_name 给），
 * 档位值保留上游原文不做中文化。
 */

/**
 * 表单态的参数值。
 * - maxTokens 为 null = 不限制输出长度（不向后端发 max_tokens）
 * - reasoningEffort 为 null = 不发这个参数，由模型自己的默认决定开不开思考
 */
export interface ModelParamsValue {
  temperature: number
  maxTokens: number | null
  reasoningEffort: string | null
}

/** 打开「限制输出长度」时给 max_tokens 的初值 */
const DEFAULT_MAX_TOKENS = 2048

/**
 * 「不设置」这一项的哨兵值 —— Radix Select 不接受空字符串当 value，
 * 而 null 又要能跟真实档位区分开（"跟随模型" ≠ "off 显式关闭"）。
 * 取名 default 不会跟档位撞（档位是 off / low / high / max）。
 */
const EFFORT_UNSET = 'default'

/** 后端 params → 表单值（缺省：temperature 1、不限制长度、思考档位不设置） */
export function fromApiParams(params?: ModelParams | null): ModelParamsValue {
  return {
    temperature: params?.temperature ?? 1,
    maxTokens: params?.max_tokens ?? null,
    reasoningEffort: params?.reasoning_effort ?? null,
  }
}

/** 表单值 → 后端 params（为 null 的字段整个省略，不向后端发） */
export function toApiParams(value: ModelParamsValue): ModelParams {
  return {
    temperature: value.temperature,
    ...(value.maxTokens !== null ? { max_tokens: value.maxTokens } : {}),
    ...(value.reasoningEffort !== null
      ? { reasoning_effort: value.reasoningEffort }
      : {}),
  }
}

interface ModelParamsFieldsProps {
  value: ModelParamsValue
  onChange: (next: ModelParamsValue) => void
  /**
   * 当前模型支持的思考档位（`AIModel.reasoning_levels`）。
   * 空 / 未传 = 不画这个控件（非推理模型、或后端不认识这个 model_name）。
   */
  reasoningLevels?: string[]
}

export function ModelParamsFields({
  value,
  onChange,
  reasoningLevels,
}: ModelParamsFieldsProps) {
  const capped = value.maxTokens !== null
  const supportsReasoning = (reasoningLevels?.length ?? 0) > 0

  return (
    <div className="space-y-5">
      {supportsReasoning && (
        <div className="space-y-2">
          <Label className="text-xs">reasoning_effort</Label>
          <Select
            value={value.reasoningEffort ?? EFFORT_UNSET}
            onValueChange={(v) =>
              onChange({
                ...value,
                reasoningEffort: v === EFFORT_UNSET ? null : v,
              })
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={EFFORT_UNSET}>{EFFORT_UNSET}</SelectItem>
              {reasoningLevels?.map((level) => (
                <SelectItem key={level} value={level}>
                  {level}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <SliderRow
        label="temperature"
        value={value.temperature}
        min={0}
        max={2}
        step={0.1}
        onChange={(temperature) => onChange({ ...value, temperature })}
      />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-xs">限制输出长度</Label>
          <Switch
            checked={capped}
            onCheckedChange={(on) =>
              onChange({ ...value, maxTokens: on ? DEFAULT_MAX_TOKENS : null })
            }
          />
        </div>
        {capped && (
          <SliderRow
            label="max_tokens"
            value={value.maxTokens as number}
            min={256}
            max={8192}
            step={256}
            onChange={(maxTokens) => onChange({ ...value, maxTokens })}
          />
        )}
      </div>
    </div>
  )
}

/** Slider + 当前值显示，拖动随动即落 form（保存按钮才提交后端） */
function SliderRow({
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
  // step >= 1 → 整数；step < 0.1 → 两位小数；其它 → 一位小数
  const decimals = step >= 1 ? 0 : step < 0.1 ? 2 : 1
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{label}</Label>
        <span className="text-muted-foreground font-mono text-xs tabular-nums">
          {value.toFixed(decimals)}
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
