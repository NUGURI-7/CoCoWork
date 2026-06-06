<template>
  <div class="shrink-0 px-4 py-4 pb-8">
    <div class="max-w-[820px] mx-auto">
      <div
        class="flex flex-col gap-2 rounded-2xl border border-border bg-background px-4 py-3 focus-within:border-ring transition-colors"
      >
        <!-- 第一行：textarea -->
        <textarea
          v-model="input"
          rows="1"
          placeholder="发送消息..."
          class="resize-none bg-transparent outline-none placeholder:text-muted-foreground max-h-40 min-h-[24px]"
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
          @keydown.enter.exact="handleEnter"
          @input="autoResize"
          ref="textareaRef"
        ></textarea>

        <!-- 第二行：左侧占位（将来 + 附件按钮等）、右侧模型选择 + 发送 -->
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-1">
            <!-- 预留：+ 按钮、附件、工具等 -->
          </div>

          <div class="flex items-center gap-2">
            <!-- 模型选择器 -->
            <Popover>
              <PopoverTrigger as-child>
                <button
                  type="button"
                  class="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <span>{{ currentModel.label }}</span>
                  <PhCaretUpDown :size="12" />
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" class="w-56 p-1">
                <button
                  v-for="m in MODEL_OPTIONS"
                  :key="`${m.provider}:${m.model}`"
                  type="button"
                  class="flex items-center justify-between w-full px-2 py-1.5 rounded-md text-sm hover:bg-muted transition-colors cursor-pointer text-left"
                  :class="{ 'bg-muted': isCurrent(m) }"
                  @click="selectModel(m)"
                >
                  <div class="flex flex-col">
                    <span class="font-medium">{{ m.label }}</span>
                    <span class="text-xs text-muted-foreground">{{ m.provider }}</span>
                  </div>
                  <PhCheck v-if="isCurrent(m)" :size="14" class="text-primary" />
                </button>
              </PopoverContent>
            </Popover>

            <!-- 发送按钮 -->
            <button
              type="button"
              :disabled="chat.isLoading || !input.trim()"
              class="shrink-0 rounded-lg p-2 bg-primary text-primary-foreground disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary/90 transition"
              @click="handleSend"
            >
              <PhPaperPlaneTilt :size="18" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { PhPaperPlaneTilt, PhCaretUpDown, PhCheck } from '@phosphor-icons/vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { v4 as uuidv4 } from 'uuid'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

// ============ 模型配置 ============
type ModelOption = {
  provider: 'deepseek' | 'gemini'
  model: string
  label: string
}

const MODEL_OPTIONS: ModelOption[] = [
  { provider: 'deepseek', model: 'deepseek-chat', label: 'DeepSeek Chat' },
  { provider: 'gemini', model: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { provider: 'gemini', model: 'gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { provider: 'gemini', model: 'gemini-3.1-flash-lite-preview', label: 'Gemini 3.1 Flash-Lite' },
  { provider: 'gemini', model: 'gemini-3.1-flash-image-preview', label: 'Nano Banana 2' },
  { provider: 'gemini', model: 'gemini-3-pro-image-preview', label: 'Nano Banana Pro' },
]

const STORAGE_KEY = 'chat:selectedModel'

function loadInitialModel(): ModelOption {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return MODEL_OPTIONS[0]!
    const saved = JSON.parse(raw)
    const matched = MODEL_OPTIONS.find(
      (m) => m.provider === saved.provider && m.model === saved.model,
    )
    return matched ?? MODEL_OPTIONS[0]!
  } catch {
    return MODEL_OPTIONS[0]!
  }
}

const currentModel = ref<ModelOption>(loadInitialModel())

watch(
  currentModel,
  (m) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ provider: m.provider, model: m.model }))
  },
  { deep: true },
)

function isCurrent(m: ModelOption) {
  return m.provider === currentModel.value.provider && m.model === currentModel.value.model
}

function selectModel(m: ModelOption) {
  currentModel.value = m
}

// ============ 原有逻辑 ============
const chat = useChatStore()
const route = useRoute()
const router = useRouter()

const input = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const isComposing = ref(false)
const isSending = ref(false)

const handleEnter = (e: KeyboardEvent) => {
  if (isComposing.value) return
  e.preventDefault()
  handleSend()
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

async function handleSend() {
  const contentToSend = input.value.trim()
  if (!contentToSend || chat.isLoading || isSending.value) return

  try {
    isSending.value = true
    input.value = ''
    await nextTick()
    autoResize()
    textareaRef.value?.focus()

    if (!route.params.uuid && chat.currentConversationUuid) {
      router.push(`/chat/${chat.currentConversationUuid}`)
    }

    await chat.sendMessage({
      message_uuid: uuidv4(),
      content: contentToSend,
      provider: currentModel.value.provider,
      model: currentModel.value.model,
    })
  } finally {
    isSending.value = false
  }
}
</script>
