<script setup lang="ts">
/**
 * 登录 / 注册共用双栏布局壳（Claude 风）
 *  - 顶部：logo wordmark（左）+ nav-action slot（右，放切换链接）
 *  - 左列：default slot（表单内容）
 *  - 右列：gopher 视觉卡（lg 以上显示）
 */
</script>

<template>
  <div class="bg-background flex min-h-dvh flex-col duration-500 animate-in fade-in">
    <!-- 顶部 nav -->
    <header class="flex h-16 items-center justify-between px-6 lg:px-10">
      <RouterLink to="/" class="flex items-center gap-2">
        <img src="/mark-rotating.svg" class="size-7" alt="CoCoWork" />
        <span class="font-serif text-xl tracking-tight">CoCoWork</span>
      </RouterLink>
      <slot name="nav-action" />
    </header>

    <!-- 主体双栏 -->
    <div class="mx-auto grid min-h-0 w-full max-w-7xl flex-1 pb-16 lg:grid-cols-2">
      <!-- 左列：表单 -->
      <div class="flex items-center justify-center px-6 py-10 lg:px-16">
        <div class="w-full max-w-sm">
          <slot />
        </div>
      </div>

      <!-- 右列：两张 gopher 错落叠放（lg+，无卡片背景） -->
      <div class="hidden items-center justify-center p-10 lg:flex">
        <div class="relative aspect-square w-full max-w-lg">
          <!-- 背景图：右上，偏小，向中间靠 -->
          <img
            src="/gopher-fcb-glass.png"
            class="absolute top-[4%] right-0 w-[58%] object-contain duration-700 animate-in fade-in zoom-in-95"
            alt="CoCoWork mascot"
          />
          <!-- 前景图：左下，偏大，向中间靠，叠在上层 + 投影 -->
          <img
            src="/gopher-dao.png"
            class="absolute bottom-[2%] left-0 z-10 w-[66%] object-contain drop-shadow-xl fill-mode-both delay-150 duration-700 animate-in fade-in slide-in-from-bottom-4"
            alt="CoCoWork mascot"
          />
        </div>
      </div>
    </div>
  </div>
</template>
