# CoCoWork Design Tokens 规范

> 本文件定义 CoCoWork 前端的完整设计规范，覆盖颜色、字体、圆角、阴影、动画、间距、层级、焦点、滚动条和暗色模式。
> 所有 CSS 变量的实际定义在 `frontend/src/app.css`，本文档是人类可读版本。

---

## 1. 颜色体系（Color Tokens）

采用 shadcn-vue 的 `background / foreground` 配对命名，所有值使用 oklch 色彩空间。
视觉风格：中性底色 + 绿色主色调，企业级管理平台风格。

### 1.1 核心变量（Light Mode）

| Token | oklch 值 | 近似色 | 用途 |
|-------|----------|--------|------|
| `--background` | `1 0 0` | 纯白 | 页面底色 |
| `--foreground` | `0.145 0 0` | 近黑 | 正文文字 |
| `--card` | `1 0 0` | 纯白 | 卡片底色 |
| `--card-foreground` | `0.145 0 0` | 近黑 | 卡片文字 |
| `--popover` | `1 0 0` | 纯白 | 浮层/下拉菜单底色 |
| `--popover-foreground` | `0.145 0 0` | 近黑 | 浮层文字 |
| `--primary` | `0.62 0.17 149` | 浅绿 | 主色（按钮、链接、强调） |
| `--primary-foreground` | `0.985 0 0` | 白 | 主色上的文字 |
| `--secondary` | `0.97 0 0` | 浅灰 | 次要表面 |
| `--secondary-foreground` | `0.205 0 0` | 深灰 | 次要表面文字 |
| `--muted` | `0.965 0 0` | 浅灰 | 弱化区域底色、禁用态 |
| `--muted-foreground` | `0.556 0 0` | 中灰 | placeholder、辅助文字 |
| `--accent` | `0.965 0 0` | 浅灰 | Hover 高亮、选中项底色 |
| `--accent-foreground` | `0.205 0 0` | 深灰 | 高亮项文字 |
| `--destructive` | `0.577 0.245 27.325` | 红色 | 删除、错误操作 |
| `--border` | `0.922 0 0` | 浅灰 | 边框、分割线 |
| `--input` | `0.922 0 0` | 浅灰 | 输入框边框 |
| `--ring` | `0.62 0.17 149` | 浅绿 | 焦点环（同 primary） |

### 1.2 品牌色

| Token | 值 | 用途 |
|-------|------|------|
| `--color-brand` | `#2f6b53`（深墨绿） | 流式指示、品牌标识、特殊场景专用，不进主题系统 |

### 1.3 状态色扩展（shadcn-vue 默认不含）

| Token | oklch 值 | 近似色 | 用途 |
|-------|----------|--------|------|
| `--info` | `0.70 0.10 230` | 蓝 | 信息提示 |
| `--info-foreground` | `0.985 0 0` | 白 | 信息文字 |
| `--success` | `0.65 0.15 145` | 绿 | 成功状态 |
| `--success-foreground` | `0.985 0 0` | 白 | 成功文字 |
| `--warning` | `0.75 0.12 80` | 金色 | 警告 |
| `--warning-foreground` | `0.25 0 0` | 深色 | 警告文字 |

### 1.4 Sidebar 专属变量

| Token | oklch 值 | 用途 |
|-------|----------|------|
| `--sidebar` | `0.975 0.005 150` | 侧边栏底色（微绿调） |
| `--sidebar-foreground` | `0.145 0 0` | 侧边栏文字 |
| `--sidebar-primary` | `0.62 0.17 149` | 侧边栏主色 |
| `--sidebar-primary-foreground` | `0.985 0 0` | 侧边栏主色文字 |
| `--sidebar-accent` | `0.94 0.015 150` | 侧边栏 hover 底色 |
| `--sidebar-accent-foreground` | `0.205 0 0` | 侧边栏 hover 文字 |
| `--sidebar-border` | `0.91 0.01 150` | 侧边栏边框 |
| `--sidebar-ring` | `0.62 0.17 149` | 侧边栏焦点环 |

### 1.5 图表色

| Token | oklch 值 | 色调 |
|-------|----------|------|
| `--chart-1` | `0.62 0.17 149` | 主绿 |
| `--chart-2` | `0.62 0.214 259` | 蓝 |
| `--chart-3` | `0.705 0.213 47` | 橙 |
| `--chart-4` | `0.606 0.25 292` | 紫 |
| `--chart-5` | `0.585 0.22 17.5` | 玫红 |

---

## 2. 字体规范（Typography）

### 2.1 字体族

```
Sans:  "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif
Mono:  "JetBrains Mono", ui-monospace, "SF Mono", monospace
```

Inter 通过 Google Fonts 或 `@fontsource/inter` 加载。如果暂不引入 Web Font，系统字体栈本身也够用。

### 2.2 字号层级

| 级别 | Tailwind 类 | 像素 | 用途 |
|------|-------------|------|------|
| 标题 | `text-2xl` | 24px | 页面大标题（登录、注册） |
| 正文 | `text-sm` | 14px | 绝大多数 UI 文字、表单标签、按钮 |
| 辅助 | `text-xs` | 12px | 时间戳、元数据、徽章 |
| 编辑器/富文本 | `text-base` | 16px | 富文本编辑区域正文 |

**规则**：不使用 `text-lg`、`text-xl`、`text-3xl` 及以上。保持极简的 3 级层级。

### 2.3 字重约定

| Tailwind 类 | 数值 | 用途 |
|-------------|------|------|
| `font-normal` | 400 | 正文默认（不需要显式声明） |
| `font-medium` | 500 | 标签、按钮文字、工具栏标题 |
| `font-semibold` | 600 | 徽章、强调元数据 |
| `font-bold` | 700 | 仅用于页面大标题 |

### 2.4 行高

使用 Tailwind 默认值。仅在以下场景手动指定：
- `leading-none`：紧凑标签（sidebar 用户名、徽章）
- `leading-relaxed`：长段落辅助文字

---

## 3. 圆角（Border Radius）

全局基准值：`--radius: 0.5rem`（8px）

shadcn-vue 组件从这个基准派生 4 个等级：

| 变量 | 值 | Tailwind 类 | 用途 |
|------|------|-------------|------|
| `--radius-sm` | `calc(--radius - 4px)` = 4px | `rounded-sm` | 小徽章、标签 |
| `--radius-md` | `--radius` = 8px | `rounded-md` | 按钮、输入框、卡片 |
| `--radius-lg` | `calc(--radius + 4px)` = 12px | `rounded-lg` | 大卡片、对话框 |
| `--radius-xl` | `calc(--radius + 8px)` = 16px | `rounded-xl` | 装饰性元素 |

---

## 4. 阴影（Shadows）

3 级极简阴影，使用中性色调：

| 级别 | CSS 值 | 用途 |
|------|--------|------|
| `shadow-sm` | `0 1px 2px oklch(0 0 0 / 0.04)` | 分割线手柄、浮动工具栏图标 |
| `shadow-md` | `0 2px 8px oklch(0 0 0 / 0.06)` | 下拉菜单、弹出层、Toast |
| `shadow-lg` | `0 4px 16px oklch(0 0 0 / 0.08)` | 模态对话框 |

**规则**：不使用 `shadow-xl` 及以上。保持克制的阴影风格。

---

## 5. 过渡动画（Transitions & Animations）

### 5.1 过渡时长

| 变量 | 值 | 用途 |
|------|------|------|
| `--transition-fast` | `150ms ease` | hover 变色、按钮按下 |
| `--transition-normal` | `200ms ease` | 侧边栏展开/折叠、面板切换 |
| `--transition-slow` | `300ms ease` | 页面级过渡 |

### 5.2 入场动画

| @keyframes | @utility 类 | 时长 | 用途 |
|------------|-------------|------|------|
| `fade-in` | `animate-fade-in` | 300ms | 渐显 |
| `slide-up` | `animate-slide-up` | 400ms | 从下滑入（表单字段） |
| `slide-down` | `animate-slide-down` | 300ms | 从上滑入（错误提示） |
| `slide-in-right` | `animate-slide-in-right` | 500ms | 从右滑入（装饰区域） |
| `gentle-float` | `animate-gentle-float` | 3s infinite | 微弱上下浮动（logo） |
| `scale-in` | `animate-scale-in` | 400ms | 缩放弹入（卡片） |

### 5.3 交错延迟

| @utility 类 | 延迟 |
|-------------|------|
| `stagger-1` | 80ms |
| `stagger-2` | 160ms |
| `stagger-3` | 240ms |
| `stagger-4` | 320ms |
| `stagger-5` | 400ms |

---

## 6. 间距约定（Spacing）

使用 Tailwind 默认间距，不自定义。以下为约定俗成的用法：

| 场景 | 推荐值 | 像素 |
|------|--------|------|
| 页面水平边距 | `px-4` ~ `px-6` | 16-24px |
| 页面垂直内容区 | `py-8` | 32px |
| 卡片内边距 | `p-4` ~ `p-6` | 16-24px |
| 列表项内边距 | `p-2` ~ `p-3` | 8-12px |
| 按钮水平内边距 | `px-3` ~ `px-4` | 12-16px |
| 紧凑 Flex 间距 | `gap-1.5` ~ `gap-2` | 6-8px |
| 表单字段间距 | `gap-3` | 12px |
| 分区间距 | `gap-4` | 16px |

**原则**：优先用父容器的 `gap-*` 控制子元素间距，避免在子元素上加 `m-*`。

---

## 7. Z-index 层级

| 层级 | 值 | 用途 |
|------|------|------|
| 内容叠层 | `z-10` | 顶部栏、分割线手柄 |
| Sidebar 遮罩 | `z-40` | 移动端 sidebar 背景遮罩 |
| 浮层 | `z-50` | 下拉菜单、Popover（shadcn-vue 管理） |
| 对话框 | `z-50` | Dialog/Modal（shadcn-vue 管理） |
| Toast | `z-[100]` | Sonner Toast（最上层） |

**规则**：大部分浮层 z-index 由 shadcn-vue 的 Reka UI 内部管理，不需要手动指定。

---

## 8. 焦点环（Focus Ring）

### 统一模式

```
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2
```

### 变体

| 场景 | ring 颜色 |
|------|-----------|
| 默认交互元素 | `ring-ring/50` |
| 破坏性操作按钮 | `ring-destructive/50` |
| 输入框 | 由 shadcn-vue `<Input>` 内置处理 |

**规则**：ring 宽度固定为 `ring-2`，不使用 `ring-1` 或 `ring-4`。

---

## 9. 滚动条

全局自定义细滚动条，颜色引用 `--border` 变量：

- 宽度：6px（横向同）
- 轨道：透明
- 滑块：`var(--border)` 的 60% 不透明度
- 滑块 hover：`var(--border)` 全不透明

Firefox 使用 `scrollbar-width: thin` + `scrollbar-color`。

---

## 10. 暗色模式

### 机制

- Light mode：`:root` 中的默认值
- Dark mode：`.dark` class 中覆盖同名变量
- 切换方式：`document.documentElement.classList.toggle('dark')`
- `color-scheme` 声明：`:root { color-scheme: light }` / `.dark { color-scheme: dark }`

### 当前状态

- `.dark` 变量集预填在 `app.css` 中（随前端初始化时落地）
- UI 中暂不暴露切换入口

---

## 维护规则

- 所有颜色值集中在 `app.css` 的 `:root` / `.dark` 中，不在组件内硬编码
- 新增语义色时，必须同时更新 `:root`、`.dark`、`@theme inline` 三处
- 本文档与 `app.css` 保持同步，修改其一必须更新另一个
