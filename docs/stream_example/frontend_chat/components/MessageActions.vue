<template>
  <div class="flex items-center gap-1">
    <button
      @click="handleCopy"
      class="flex items-center justify-center p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
      :title="copied ? '已复制' : '复制'"
    >
      <PhCheck v-if="copied" :size="16" class="text-success" />
      <PhCopy v-else :size="16" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { PhCopy, PhCheck } from '@phosphor-icons/vue'
import { copyToClipboard } from '@/utils/clipboard'

const props = defineProps<{
  content: string
  role: 'user' | 'assistant'
}>()

const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const handleCopy = async () => {
  if (!props.content) return

  if (timer) {
    clearTimeout(timer)
    timer = null
  }

  try {
    await copyToClipboard(props.content)
    copied.value = true
    timer = setTimeout(() => {
      copied.value = false
      timer = null
    }, 1500)
  } catch (err) {
    console.error('复制失败:', err)
  }
}

onUnmounted(() => {
  if (timer) clearTimeout(timer)
})
</script>
