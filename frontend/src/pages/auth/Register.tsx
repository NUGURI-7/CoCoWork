import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Contact, Loader2, Lock, Mail, User } from 'lucide-react'
import { Link, useNavigate } from '@tanstack/react-router'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import * as authApi from '@/api/auth'
import { ApiBusinessError } from '@/request'
import AuthShell from './AuthShell'
import IconField from './IconField'

const formSchema = z.object({
  username: z
    .string()
    .min(3, '用户名至少 3 个字符')
    .max(20, '用户名最多 20 个字符')
    .regex(/^[a-zA-Z0-9_]+$/, '只能包含字母、数字、下划线'),
  email: z.string().email('请输入有效的邮箱地址'),
  nick_name: z.string().min(2, '昵称至少 2 个字符').max(50, '昵称最多 50 个字符'),
  password: z.string().min(6, '密码至少 6 个字符').max(64, '密码最多 64 个字符'),
})

type FormValues = z.infer<typeof formSchema>

export default function Register() {
  const navigate = useNavigate()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { username: '', email: '', nick_name: '', password: '' },
  })

  const onSubmit = async (values: FormValues) => {
    try {
      await authApi.register(values)
      toast.success('注册成功，请登录')
      navigate({ to: '/login' })
    } catch (e) {
      toast.error(e instanceof ApiBusinessError ? e.message : '注册失败，请稍后重试')
    }
  }

  return (
    <AuthShell
      navAction={
        <Link
          to="/login"
          className="text-muted-foreground hover:text-foreground text-sm transition-colors"
        >
          已有账号？<span className="text-foreground font-medium">登录</span>
        </Link>
      }
    >
      <div className="space-y-8">
        {/* 标题 */}
        <div className="space-y-3 duration-700 animate-in slide-in-from-bottom-3">
          <h1 className="font-display text-5xl leading-[1.05] font-medium tracking-tight lg:text-6xl">
            Start building
            <br />
            today
          </h1>
          <p className="text-muted-foreground text-sm">Create your CoCoWork account</p>
        </div>

        {/* 表单卡片 */}
        <Card className="border-border/60 fill-mode-both shadow-lg delay-150 duration-700 animate-in slide-in-from-bottom-3">
          <CardContent>
            <Form {...form}>
              <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>用户名</FormLabel>
                      <IconField icon={User}>
                        <FormControl>
                          <Input
                            type="text"
                            placeholder="字母、数字、下划线"
                            autoComplete="username"
                            className="h-10 pl-9"
                            {...field}
                          />
                        </FormControl>
                      </IconField>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>邮箱</FormLabel>
                      <IconField icon={Mail}>
                        <FormControl>
                          <Input
                            type="email"
                            placeholder="you@example.com"
                            autoComplete="email"
                            className="h-10 pl-9"
                            {...field}
                          />
                        </FormControl>
                      </IconField>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="nick_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>昵称</FormLabel>
                      <IconField icon={Contact}>
                        <FormControl>
                          <Input
                            type="text"
                            placeholder="显示名称"
                            autoComplete="nickname"
                            className="h-10 pl-9"
                            {...field}
                          />
                        </FormControl>
                      </IconField>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>密码</FormLabel>
                      <IconField icon={Lock}>
                        <FormControl>
                          <Input
                            type="password"
                            placeholder="至少 6 个字符"
                            autoComplete="new-password"
                            className="h-10 pl-9"
                            {...field}
                          />
                        </FormControl>
                      </IconField>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  className="h-10 w-full"
                  disabled={form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />}
                  注册
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </AuthShell>
  )
}
