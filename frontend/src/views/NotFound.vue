<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="grid min-h-dvh place-items-center p-8">
    <div class="text-center">
      <p class="text-muted-foreground text-sm tracking-widest uppercase">404</p>
      <h1 class="font-serif mt-2 text-5xl">页面不存在</h1>
      <p class="text-muted-foreground mt-3 text-sm">该路径不存在或已被移除。</p>
      <button
        class="bg-primary text-primary-foreground hover:bg-primary/90 mt-8 rounded-md px-5 py-2 text-sm transition"
        @click="router.push('/')"
      >
        返回主页
      </button>
    </div>
  </div>
</template>
