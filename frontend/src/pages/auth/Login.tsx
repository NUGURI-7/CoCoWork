import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Loader2, Lock, User } from 'lucide-react'
import { Link, useNavigate } from '@tanstack/react-router'
import { Route as LoginRoute } from '@/routes/login'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth'
import { ApiBusinessError } from '@/request'
import AuthShell from './AuthShell'
import IconField from './IconField'

const formSchema = z.object({
  username: z
    .string()
    .min(3, '用户名至少 3 个字符')
    .max(20, '用户名最多 20 个字符')
    .regex(/^[a-zA-Z0-9_]+$/, '只能包含字母、数字、下划线'),
  password: z.string().min(6, '密码至少 6 个字符').max(64, '密码最多 64 个字符'),
})

type FormValues = z.infer<typeof formSchema>

export default function Login() {
  const navigate = useNavigate()
  const search = LoginRoute.useSearch()
  const login = useAuthStore((s) => s.login)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { username: '', password: '' },
  })

  const onSubmit = async (values: FormValues) => {
    try {
      await login(values)
      const redirect = search.redirect || '/'
      navigate({ to: redirect })
    } catch (e) {
      toast.error(e instanceof ApiBusinessError ? e.message : '登录失败，请稍后重试')
    }
  }

  return (
    <AuthShell
      navAction={
        <Link
          to="/register"
          className="text-muted-foreground hover:text-foreground text-sm transition-colors"
        >
          还没账号？<span className="text-foreground font-medium">注册</span>
        </Link>
      }
    >
      <div className="space-y-8">
        {/* 标题 */}
        <div className="space-y-3 duration-700 animate-in slide-in-from-bottom-3">
          <h1 className="font-display text-5xl leading-[1.05] font-medium tracking-tight lg:text-6xl">
            Think fast,
            <br />
            build faster
          </h1>
          <p className="text-muted-foreground text-sm">Brainstorm in chat, build in Cowork</p>
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
                            placeholder="输入用户名"
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
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>密码</FormLabel>
                      <IconField icon={Lock}>
                        <FormControl>
                          <Input
                            type="password"
                            placeholder="输入密码"
                            autoComplete="current-password"
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
                  登录
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </AuthShell>
  )
}
