<template>
  <div class="h-full">
    <ChatPanel></ChatPanel>
  </div>
</template>
<script setup lang="ts">
import ChatPanel from '../frontend_chat/components/ChatPanel.vue'

defineOptions({ name: 'Chat' })
</script>
