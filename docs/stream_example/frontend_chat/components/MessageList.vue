<template>
  <div
    ref="scrollContainer"
    class="relative flex-1 min-h-0 overflow-y-auto px-4 pt-6"
    tabindex="-1"
    @wheel.passive="handleUserIntent"
    @touchmove.passive="handleUserIntent"
    @scroll.passive="handleScroll"
    @keydown="handleKeydown"
  >
    <div ref="innerContainer" class="max-w-3xl mx-auto space-y-6">
      <div v-for="(msg, index) in chat.messages" :key="msg.uuid" class="group/msg">
        <!-- User 消息 -->
        <div v-if="msg.role === 'user'" class="flex flex-col items-end gap-1">
          <div class="max-w-[80%] rounded-2xl bg-muted text-foreground px-4 py-2.5">
            <MarkdownRender :content="msg.content" :is-user="true" />
          </div>
          <MessageActions
            :content="getMessageMarkdown(msg)"
            role="user"
            :class="[
              'mt-1 transition-opacity duration-150',
              isLastMessage(index) ? 'opacity-100' : 'opacity-0 group-hover/msg:opacity-100',
            ]"
          />
        </div>

        <!-- Assistant 消息 -->
        <div v-else class="flex flex-col gap-2">
          <template v-for="block in msg.blocks" :key="block.index">
            <TextBlock v-if="block.type === 'text'" :block="block" />
            <ToolUseBlock v-else-if="block.type === 'tool_use'" :block="block" />
            <ImageBlock v-else-if="block.type === 'image'" :block="block" />
          </template>

          <!-- 1. Error Message 放最上面 (如果有的话) -->
          <p v-if="msg.status === 'error'" class="text-destructive text-sm">
            {{ msg.errorMessage }}
          </p>

          <!-- 2. MessageActions (Copy按钮) 放在紧接着文本的下方 -->
          <!-- 流式期间不显示，避免复制到半截 -->
          <MessageActions
            v-if="msg.status !== 'streaming'"
            :content="getMessageMarkdown(msg)"
            role="assistant"
            :class="[
              'mt-1 transition-opacity duration-150',
              isLastMessage(index) ? 'opacity-100' : 'opacity-0 group-hover/msg:opacity-100',
            ]"
          />

          <!-- 3. Icon (ThreeSpinner) 放在最底部，并使用独立的 margin 和位置偏移打破包裹感 -->
          <div
            v-if="msg.status === 'streaming' || msg.uuid === chat.lastAssistantUuid"
            class="mt-2 -ml-2.5"
          >
            <ThreeSpinner :size="36" :active="msg.status === 'streaming'" />
          </div>
        </div>
      </div>
      <div ref="scrollAnchor" class="h-10 w-full shrink-0"></div>
    </div>
    <!-- 悬浮回到最新按钮 -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-2"
    >
      <div
        v-if="!isAutoScrolling"
        class="sticky bottom-2 flex justify-center w-full pointer-events-none"
      >
        <button
          @click="resumeAutoScroll"
          class="flex items-center justify-center w-8 h-8 rounded-full bg-background border border-border shadow-md text-muted-foreground hover:text-foreground cursor-pointer pointer-events-auto transition-colors"
          title="回到最新"
        >
          <PhArrowDown :size="16" />
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, useTemplateRef, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useResizeObserver } from '@vueuse/core'
import { PhArrowDown } from '@phosphor-icons/vue'
import TextBlock from './blocks/TextBlock.vue'
import ToolUseBlock from './blocks/ToolUseBlock.vue'
import ImageBlock from './blocks/ImageBlock.vue'
import type { ChatMessage, RenderBlock } from '@/types/chat'
import ThreeSpinner from '@/components/common/ThreeSpinner.vue'
import MarkdownRender from './MarkdownRender.vue'
import MessageActions from './MessageActions.vue'
import { getMessageMarkdown } from '@/utils/messageContent'

const chat = useChatStore()

// 判断当前消息是否应该被视为"列表中最新的可见消息"
// 特殊情况：如果最后一条是流式中的 AI 消息，那它隐藏着 action bar，
// 此时倒数第二条（user）才是视觉上的"最后一条"
function isLastMessage(index: number): boolean {
  const total = chat.messages.length
  const last = chat.messages[total - 1]

  if (last && last.role === 'assistant' && last.status === 'streaming') {
    return index === total - 2
  }
  return index === total - 1
}

// ==========================================
// 智能滚动逻辑
// ==========================================
const scrollContainer = useTemplateRef<HTMLElement>('scrollContainer')
const innerContainer = useTemplateRef<HTMLElement>('innerContainer')
const scrollAnchor = useTemplateRef<HTMLElement>('scrollAnchor')

// 是否处于自动跟随状态
const isAutoScrolling = ref(true)

// 执行滚动 (终极版)
const scrollToBottom = (behavior: 'auto' | 'smooth' | 'instant' = 'instant') => {
  if (!scrollContainer.value) return
  // 不管它算出来多高，哪怕算错了，我们直接加一个 100 万的像素进去
  // 浏览器底层 C++ 代码会自动把它裁剪到真正的物理极限
  const maxLimit = scrollContainer.value.scrollHeight + 1000000
  scrollContainer.value.scrollTo({
    top: maxLimit,
    behavior: behavior === 'instant' ? 'auto' : behavior,
  })
}

// 用户主动干预：滚轮或触摸滑动 (终极版)
const handleUserIntent = () => {
  if (!scrollContainer.value) return

  const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value

  // 给一个宽容的保护罩，比如 20px
  const isAtBottom = scrollHeight - scrollTop - clientHeight <= 20

  // 【核心防御】：如果你此时处在最底部（或者刚被代码拉到底部），
  // 哪怕你手抖转了滚轮，我也假装没看见！绝对不打断你的自动跟随！
  if (isAtBottom) {
    return
  }

  // 只有当你明显不在底部时，转滚轮才算是“我要看上面”
  isAutoScrolling.value = false
}

// 用户主动干预：键盘导航键
const handleKeydown = (e: KeyboardEvent) => {
  if (['PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) {
    handleUserIntent()
  }
}

// 唯一判定触底的逻辑 (终极版)
const handleScroll = () => {
  if (!scrollContainer.value) return

  const scrollTop = Math.ceil(scrollContainer.value.scrollTop)
  const scrollHeight = scrollContainer.value.scrollHeight
  const clientHeight = scrollContainer.value.clientHeight

  // 这里也用 20px
  const isNearBottom = scrollHeight - scrollTop - clientHeight <= 20

  if (isNearBottom && !isAutoScrolling.value) {
    isAutoScrolling.value = true
  }
}

// 点击悬浮按钮：恢复跟随并平滑滚动
const resumeAutoScroll = () => {
  isAutoScrolling.value = true
  scrollToBottom('smooth')
}

// 核心驱动：监听内容区的高度变化
useResizeObserver(innerContainer, () => {
  if (isAutoScrolling.value) {
    scrollToBottom('instant')
  }
})

// 强干预：发送新消息时强制接管，并处理初始加载
watch(
  () => chat.messages.length,
  (newLen, oldLen) => {
    if (newLen === 0) return

    const lastMsg = chat.messages[newLen - 1]
    const isNewUserMessage = lastMsg?.role === 'user'
    const isInitialLoad = oldLen === 0 && newLen > 0

    if (isNewUserMessage || isInitialLoad) {
      isAutoScrolling.value = true
      nextTick(() => {
        scrollToBottom('instant')
      })
    }
  },
  { immediate: true },
)

onMounted(() => {
  if (chat.messages.length > 0) {
    scrollToBottom('instant')
  }
})

// 判断 block 是否是 msg 里最后一个 text block
function isLastTextBlock(msg: ChatMessage, block: RenderBlock) {
  // 1. 类型守卫：如果是 user 消息（或者没有 blocks），直接返回 false
  if (msg.role === 'user' || !('blocks' in msg)) {
    return false
  }

  // 2. 此时 TypeScript 已经自动推断 msg 是 AssistantMessage
  // 下面就不需要写 msg.blocks! 了，直接写 msg.blocks 即可
  for (let i = msg.blocks.length - 1; i >= 0; i--) {
    if (msg.blocks[i]!.type === 'text') {
      return msg.blocks[i]!.index === block.index
    }
  }

  return false
}
</script>
