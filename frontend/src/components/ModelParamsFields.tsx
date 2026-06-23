import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import type { ModelParams } from '@/types'

/**
 * 模型调用参数编辑器 —— Agent ConfigPanel / Workspace 管家配置共用。
 *
 * temperature 常驻滑杆（默认 1 == 多数 provider 默认，无害恒发）。
 * max_tokens 走开关门控：关 = 不限制、不发参数（模型用自然上限）；开 = 出滑杆、发 max_tokens。
 * 「不发 = 不截断」是默认，避免给所有对话硬塞一个输出上限。
 */

/** 表单态的参数值。maxTokens 为 null = 不限制输出长度（不向后端发 max_tokens）。 */
export interface ModelParamsValue {
  temperature: number
  maxTokens: number | null
}

/** 打开「限制输出长度」时给 max_tokens 的初值 */
const DEFAULT_MAX_TOKENS = 2048

/** 后端 params → 表单值（缺省：temperature 1、不限制长度） */
export function fromApiParams(params?: ModelParams | null): ModelParamsValue {
  return {
    temperature: params?.temperature ?? 1,
    maxTokens: params?.max_tokens ?? null,
  }
}

/** 表单值 → 后端 params（maxTokens 为 null 时省略 max_tokens，不发上限） */
export function toApiParams(value: ModelParamsValue): ModelParams {
  return {
    temperature: value.temperature,
    ...(value.maxTokens !== null ? { max_tokens: value.maxTokens } : {}),
  }
}

interface ModelParamsFieldsProps {
  value: ModelParamsValue
  onChange: (next: ModelParamsValue) => void
}

export function ModelParamsFields({ value, onChange }: ModelParamsFieldsProps) {
  const capped = value.maxTokens !== null

  return (
    <div className="space-y-5">
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
