<!-- frontend/src/components/chat/components/MarkdownRender.vue -->
<template>
  <div ref="root" :class="containerClass" @click="handleCopyClick"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import morphdom from 'morphdom'
import { renderMarkdown } from '@/utils/markdown'
import { renderAllMermaid } from '@/utils/mermaid'
import { copyToClipboard } from '@/utils/clipboard'

const props = defineProps<{
  content: string
  isStreaming?: boolean
  isUser?: boolean
}>()

const root = ref<HTMLDivElement | null>(null)

// 容器类：AI 走标准 prose；用户消息挂 break-words 触发 pre-wrap
const containerClass = computed(() => [
  'prose prose-sm md:prose-base dark:prose-invert max-w-none',
  'prose-p:leading-relaxed prose-pre:p-0 prose-pre:m-0 prose-pre:bg-transparent',
  props.isUser ? 'break-words' : '',
])

// ==========================================
// 增量渲染（morphdom + rAF）
// ==========================================
let rafId: number | null = null
let pendingHtml = ''

const flush = () => {
  rafId = null
  if (!root.value) return

  const tmp = document.createElement('div')
  tmp.innerHTML = pendingHtml

  morphdom(root.value, tmp, {
    childrenOnly: true,
    onBeforeElUpdated(fromEl, toEl) {
      if (
        fromEl instanceof HTMLElement &&
        fromEl.classList.contains('copy-btn') &&
        fromEl.dataset.copying === '1'
      ) {
        return false
      }

      // Mermaid 容器：如果已渲染，就跳过 diff（保留 SVG）
      if (
        fromEl instanceof HTMLElement &&
        fromEl.classList.contains('mermaid-container') &&
        fromEl.dataset.mermaidRendered === '1'
      ) {
        // 但如果源码变了，就允许 diff 覆盖，重新走渲染流程
        const newSource = (toEl as HTMLElement).dataset.mermaidSource
        const oldSource = fromEl.dataset.mermaidSource
        if (newSource === oldSource) return false
      }

      if (fromEl.isEqualNode(toEl)) return false
      return true
    },
  })

  // 流式期间不渲染 Mermaid（保持 loading），流式结束后统一渲染
  if (!props.isStreaming && root.value) {
    void renderAllMermaid(root.value)
  }
}

const schedule = () => {
  if (rafId != null) return
  rafId = requestAnimationFrame(flush)
}

const update = () => {
  pendingHtml = renderMarkdown(props.content, props.isStreaming, props.isUser)
  if (props.isStreaming) {
    schedule()
  } else {
    // 非流式（历史消息 / 完成后的最终渲染）立即 flush
    if (rafId != null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    flush()
  }
}

watch(() => props.content, update)
watch(() => props.isStreaming, update)

onMounted(() => {
  pendingHtml = renderMarkdown(props.content, props.isStreaming, props.isUser)
  if (root.value) root.value.innerHTML = pendingHtml
  if (!props.isStreaming && root.value) {
    void renderAllMermaid(root.value)
  }
})

onUnmounted(() => {
  if (rafId != null) cancelAnimationFrame(rafId)
})

// ==========================================
// 事件委托：代码块复制按钮
// ==========================================
const handleCopyClick = async (event: MouseEvent) => {
  const target = event.target as HTMLElement
  const btn = target.closest('.copy-btn') as HTMLButtonElement | null
  if (!btn) return

  const codeToCopy = btn.getAttribute('data-code')
  if (!codeToCopy) return

  try {
    await copyToClipboard(codeToCopy)

    // 打标记 —— morphdom 看到后会跳过这个节点
    btn.dataset.copying = '1'
    const originalHtml = btn.innerHTML
    btn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 256 256" class="text-success"><path fill="currentColor" d="M229.66 77.66l-128 128a8 8 0 0 1-11.32 0l-56-56a8 8 0 0 1 11.32-11.32L96 188.69L218.34 66.34a8 8 0 0 1 11.32 11.32Z"/></svg>
      <span class="copy-text text-success">Copied!</span>
    `

    setTimeout(() => {
      if (!btn.isConnected) return
      btn.innerHTML = originalHtml
      delete btn.dataset.copying
    }, 1500)
  } catch (err) {
    console.error('Failed to copy code: ', err)
  }
}
</script>
