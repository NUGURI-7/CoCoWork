<!-- frontend/src/components/chat/components/blocks/ImageBlock.vue -->
<template>
  <div class="my-3 w-full">
    <!-- loading 态：占一行，居中 Trefoil + 文案 -->
    <div
      v-if="block.status === 'loading'"
      class="flex items-center justify-center gap-3 py-6 rounded-xl bg-muted/40"
    >
      <l-cardio
        size="28"
        stroke="3"
        stroke-length="0.15"
        bg-opacity="0.1"
        speed="1.4"
        color="currentColor"
      />
      <span class="text-sm text-muted-foreground">Generating image...</span>
    </div>

    <!-- ready 态：图片 -->
    <img
      v-else-if="block.status === 'ready' && block.url"
      :src="block.url"
      alt="AI generated image"
      class="max-w-full rounded-xl shadow cursor-zoom-in transition-transform hover:scale-[1.01]"
      @click="openFull"
    />

    <!-- error 态 -->
    <div
      v-else
      class="flex items-center gap-3 py-4 px-4 rounded-xl bg-destructive/10 text-destructive text-sm"
    >
      <span>Failed to generate image</span>
      <span v-if="block.errorMessage" class="opacity-70">— {{ block.errorMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { cardio } from 'ldrs'
import type { ImageBlock } from '@/types/chat'

const props = defineProps<{
  block: ImageBlock
}>()

onMounted(() => {
  // ldrs 的 web component 需要注册一次，重复注册无副作用
  cardio.register()
})

function openFull() {
  if (props.block.url) {
    window.open(props.block.url, '_blank')
  }
}
</script>
