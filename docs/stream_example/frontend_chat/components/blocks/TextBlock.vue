<!-- frontend/src/components/chat/components/blocks/TextBlock.vue -->
<template>
  <div class="text-block">
    <!-- 将原来的 <p>{{ block.content }}</p> 替换为 MarkdownRender -->
    <!-- 传入 block.content，并且当 block.status 还是 'active' 时告知组件正在流式输出，开启防抖和软闭合 -->
    <MarkdownRender :content="block.content" :is-streaming="block.status === 'active'" />
  </div>
</template>

<script setup lang="ts">
import type { TextBlock } from '@/types/chat'
import MarkdownRender from '../MarkdownRender.vue'

defineProps<{
  block: TextBlock
}>()
</script>
