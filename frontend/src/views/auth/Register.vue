<script setup lang="ts">
import { useRouter } from 'vue-router'
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
const auth = useAuthStore()

const formSchema = toTypedSchema(
  z.object({
    username: z
      .string()
      .min(3, '用户名至少 3 个字符')
      .max(20, '用户名最多 20 个字符')
      .regex(/^[a-zA-Z0-9_]+$/, '只能包含字母、数字、下划线'),
    email: z.string().email('请输入有效的邮箱地址'),
    nick_name: z.string().min(2, '昵称至少 2 个字符').max(50, '昵称最多 50 个字符'),
    password: z.string().min(6, '密码至少 6 个字符').max(64, '密码最多 64 个字符'),
  }),
)

const { handleSubmit, isSubmitting } = useForm({
  validationSchema: formSchema,
})

const onSubmit = handleSubmit(async (values) => {
  try {
    await auth.register(values)
    router.push('/')
  } catch (e) {
    toast.error(e instanceof ApiBusinessError ? e.message : '注册失败，请稍后重试')
  }
})
</script>

<template>
  <AuthShell>
    <template #nav-action>
      <RouterLink
        to="/login"
        class="text-muted-foreground hover:text-foreground text-sm transition-colors"
      >
        已有账号？<span class="text-foreground font-medium">登录</span>
      </RouterLink>
    </template>

    <div class="space-y-8">
      <!-- 标题 -->
      <div class="space-y-3 duration-700 animate-in slide-in-from-bottom-3">
        <h1 class="font-serif text-5xl leading-[1.05] lg:text-6xl">Start building<br />today</h1>
        <p class="text-muted-foreground text-sm">Create your CoCoWork account</p>
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
                placeholder="字母、数字、下划线"
                autocomplete="username"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="email">
          <FormItem>
            <FormLabel>邮箱</FormLabel>
            <FormControl>
              <Input
                type="email"
                placeholder="you@example.com"
                autocomplete="email"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="nick_name">
          <FormItem>
            <FormLabel>昵称</FormLabel>
            <FormControl>
              <Input type="text" placeholder="显示名称" autocomplete="nickname" v-bind="componentField" />
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
                placeholder="至少 6 个字符"
                autocomplete="new-password"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <Button type="submit" class="w-full" :disabled="isSubmitting">
          <Loader2 v-if="isSubmitting" class="size-4 animate-spin" />
          注册
        </Button>
      </form>
    </div>
  </AuthShell>
</template>
