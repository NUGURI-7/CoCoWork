<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import * as z from 'zod'
import { toast } from 'vue-sonner'
import { Loader2 } from 'lucide-vue-next'
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'
import { ApiBusinessError } from '@/request'
import AuthShell from './AuthShell.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formSchema = toTypedSchema(
  z.object({
    username: z
      .string()
      .min(3, '用户名至少 3 个字符')
      .max(20, '用户名最多 20 个字符')
      .regex(/^[a-zA-Z0-9_]+$/, '只能包含字母、数字、下划线'),
    password: z.string().min(6, '密码至少 6 个字符').max(64, '密码最多 64 个字符'),
  }),
)

const { handleSubmit, isSubmitting } = useForm({
  validationSchema: formSchema,
})

const onSubmit = handleSubmit(async (values) => {
  try {
    await auth.login(values)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e) {
    toast.error(e instanceof ApiBusinessError ? e.message : '登录失败，请稍后重试')
  }
})
</script>

<template>
  <AuthShell>
    <template #nav-action>
      <RouterLink
        to="/register"
        class="text-muted-foreground hover:text-foreground text-sm transition-colors"
      >
        还没账号？<span class="text-foreground font-medium">注册</span>
      </RouterLink>
    </template>

    <div class="space-y-8">
      <!-- 标题 -->
      <div class="space-y-3 duration-700 animate-in slide-in-from-bottom-3">
        <h1 class="font-serif text-5xl leading-[1.05] lg:text-6xl">Think fast,<br />build faster</h1>
        <p class="text-muted-foreground text-sm">Brainstorm in chat, build in Cowork</p>
      </div>

      <!-- 表单 -->
      <form
        class="space-y-4 fill-mode-both delay-150 duration-700 animate-in slide-in-from-bottom-3"
        @submit="onSubmit"
      >
        <FormField v-slot="{ componentField }" name="username">
          <FormItem>
            <FormLabel>用户名</FormLabel>
            <FormControl>
              <Input
                type="text"
                placeholder="输入用户名"
                autocomplete="username"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="password">
          <FormItem>
            <FormLabel>密码</FormLabel>
            <FormControl>
              <Input
                type="password"
                placeholder="输入密码"
                autocomplete="current-password"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <Button type="submit" class="w-full" :disabled="isSubmitting">
          <Loader2 v-if="isSubmitting" class="size-4 animate-spin" />
          登录
        </Button>
      </form>
    </div>
  </AuthShell>
</template>
