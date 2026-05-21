<script setup lang="ts">
import { Toaster } from '@/components/ui/sonner'
</script>

<template>
  <RouterView />
  <Toaster position="top-right" :duration="3500" close-button rich-colors />
</template>
