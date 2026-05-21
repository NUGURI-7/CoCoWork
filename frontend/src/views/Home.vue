<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  window.location.href = '/login'
}
</script>

<template>
  <main class="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-6 px-6">
    <header>
      <h1 class="font-serif text-5xl">CoCoWork</h1>
      <p class="text-muted-foreground mt-2 text-sm">登录成功 — 占位主页</p>
    </header>

    <section v-if="auth.user" class="bg-card rounded-lg border p-6">
      <h2 class="mb-3 text-sm font-medium tracking-wide uppercase">Current user</h2>
      <dl class="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
        <dt class="text-muted-foreground">username</dt>
        <dd>{{ auth.user.username }}</dd>
        <dt class="text-muted-foreground">nick_name</dt>
        <dd>{{ auth.user.nick_name }}</dd>
        <dt class="text-muted-foreground">email</dt>
        <dd>{{ auth.user.email }}</dd>
        <dt class="text-muted-foreground">is_admin</dt>
        <dd>{{ auth.user.is_admin }}</dd>
      </dl>
    </section>

    <button
      class="bg-primary text-primary-foreground hover:bg-primary/90 self-start rounded-md px-4 py-2 text-sm transition"
      @click="handleLogout"
    >
      退出登录
    </button>
  </main>
</template>
