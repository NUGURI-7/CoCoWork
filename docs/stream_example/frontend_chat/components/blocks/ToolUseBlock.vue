<template>
  <!-- self-start 让宽度跟内容走，不被父级 flex-col 撑满 -->
  <div class="self-start max-w-full">
    <!-- 头部：一行，无边框，点击折叠/展开 -->
    <button
      type="button"
      class="inline-flex items-center gap-2 max-w-full text-sm text-muted-foreground hover:text-foreground transition-colors py-1 -mx-1 px-1 rounded cursor-pointer"
      @click="collapsed = !collapsed"
    >
      <!-- 状态图标 -->
      <span class="shrink-0 flex items-center">
        <PhSpinner v-if="isRunning" :size="14" class="animate-spin" />
        <PhWrench
          v-else-if="block.status === 'success'"
          :size="14"
          weight="fill"
          class="text-brand"
        />
        <PhXCircle
          v-else-if="block.status === 'error'"
          :size="14"
          weight="fill"
          class="text-destructive"
        />
      </span>

      <!-- 工具名 -->
      <span class="shrink-0 text-foreground/80 font-medium">{{ block.name }}</span>

      <!-- 展开箭头 -->
      <PhCaretDown
        :size="12"
        class="shrink-0 transition-transform duration-200 opacity-60"
        :class="{ '-rotate-90': collapsed }"
      />
    </button>

    <!-- 详情（展开时显示，轻底色面板） -->
    <div v-if="!collapsed" class="mt-1.5 ml-5 rounded-md bg-muted/50 p-3 space-y-2 text-xs">
      <div>
        <div class="text-muted-foreground mb-1">参数</div>
        <pre
          class="bg-background/60 rounded p-2 overflow-x-auto whitespace-pre-wrap wrap-break-word"
          >{{ inputJsonText }}</pre
        >
      </div>

      <div v-if="block.resultData !== null && block.resultData !== undefined">
        <div class="text-muted-foreground mb-1">结果</div>
        <pre
          class="bg-background/60 rounded p-2 overflow-x-auto whitespace-pre-wrap wrap-break-word max-h-64"
          >{{ resultText }}</pre
        >
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PhCaretDown, PhWrench, PhSpinner, PhXCircle } from '@phosphor-icons/vue'
import type { ToolUseBlock } from '@/types/chat'

const props = defineProps<{
  block: ToolUseBlock
}>()

// 默认折叠状态跟随 block.collapsed（历史消息折叠，实时流默认展开）
const collapsed = ref(props.block.collapsed)

watch(
  () => props.block.status,
  (newStatus, oldStatus) => {
    if (
      (oldStatus === 'building' || oldStatus === 'calling') &&
      (newStatus === 'success' || newStatus === 'error')
    ) {
      collapsed.value = true
    }
  },
)

const isRunning = computed(
  () => props.block.status === 'building' || props.block.status === 'calling',
)

const inputJsonText = computed(() => {
  const raw = props.block.partialInputJson || ''
  if (!raw) return '(无参数)'
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
})

const resultText = computed(() => {
  const d = props.block.resultData
  if (d === null || d === undefined) return ''
  if (typeof d === 'string') return d
  try {
    return JSON.stringify(d, null, 2)
  } catch {
    return String(d)
  }
})
</script>
