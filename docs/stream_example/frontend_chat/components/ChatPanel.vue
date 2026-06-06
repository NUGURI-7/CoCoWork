<template>
  <div class="flex flex-col h-full min-h-0 bg-background">
    <!-- 有消息：正常的消息列表 -->
    <MessageList v-if="!isEmpty" />

    <!-- 空状态：上方 flex-1 占位 + logo + 欢迎语 -->
    <template v-if="isEmpty">
      <div class="flex-[3]" />
      <div class="flex flex-col items-center gap-4 px-4">
        <img src="/mark-rotating.svg" alt="" class="size-16 select-none pointer-events-none" />
        <p class="text-lg text-muted-foreground">How can I help you today?</p>
      </div>
    </template>

    <!-- MessageInput 始终在这个位置，不会被 rebuild -->
    <MessageInput />

    <!-- 空状态：下方 flex-1 占位，把 input 拉到中间 -->
    <div v-if="isEmpty" class="flex-[7]" />
  </div>
</template>

<script setup lang="ts">
import { watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'
import { useChatStore } from '@/stores/chat'

defineOptions({ name: 'ChatPanel' })

const route = useRoute()
const chat = useChatStore()

const isEmpty = computed(() => !chat.isLoadingConversation && chat.messages.length === 0)

// ... 保留原有 watch
watch(
  () => route.params.uuid,
  (uuid) => {
    if (typeof uuid === 'string' && uuid) {
      if (uuid === chat.currentConversationUuid) return
      chat.loadConversation(uuid)
    } else {
      chat.newConversation()
    }
  },
  { immediate: true },
)
</script>
