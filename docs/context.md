# CoCoWork Context

## 项目概述
- CoCoWork 是一个个人独立开发的 full-stack 项目，后端使用 FastAPI，前端使用 React 19。
- 当前定位：AI Agent 管理平台（暂定方向，随开发推进持续演化），核心能力包括多 Agent 编排与调度、RAG 混合检索、Prompt 版本管理、Skill 技能市场、知识库管理。
- 这个文件是后续 AI 新对话的单一项目上下文来源。

## 早期方向参考（低权重）
- 这部分只用于提供产品方向上的大致印象，帮助 AI 理解项目可能的长期演化方向。
- 这不是正式需求，不构成强约束，也不代表相关能力已经实现。
- 如果与当前代码现状、你在当次对话中的明确要求或后续决策冲突，应以实际项目状态和当前任务为准。
- 远期愿景：可管理、可编排、可扩展的一站式 Agent 平台，支持语音交互（ASR/TTS）与视觉理解多模态输入输出，提供多层 RBAC 权限管控与资源隔离。
- 当前阶段聚焦基础设施搭建和核心后端能力验证，前端仅做满足测试和验证需要的最小实现。

## 产品 / IA 决策（2026-05-22 敲定，中等权重）
- 定位：团队管理 + 个人使用；普通用户进个人工作台，admin 另有独立后台。
- 主界面：左侧 sidebar 工作台（非 chat-first）。大模块：Agent / Knowledge / Tool(待定) / Model；Prompt 并入 Agent 配置、不单列。落地页 = 个人主页(dashboard)，从主页或 sidebar 进各模块。
- 不引画布编排：声明引用 + 后端持有拓扑（LangGraph 模板 single/supervisor/pipeline，表单填槽）；多 agent = supervisor / agent-as-tool；只读拓扑图后置。
- Agent 可配置/可发布，发布后对外暴露对话，目标「统一会话内多 agent」。agent 卡片：点卡片→配置编排，点按钮→对话。
- 对话：配置页 Playground(调试) + 发布后 chat 路由(正式)。
- Knowledge 可被 agent 关联为 RAG 外挂；每库配 embedding；文档编辑用自封装 tiptap(后做)。
- skill/tool 放外置沙箱跑；用户能否上传待定；skill 暂缓。
- admin 入口藏头像下拉(仅 admin)；admin 是独立 `/admin` 分区（与工作台平级、不嵌套）。
- MVP 聚焦：先简单 agent 跑动 + RAG 混合检索；功能铺完再做 agent 能力/检索准确度/调度执行优化。

## 技术栈
- Backend: FastAPI, Tortoise ORM, PostgreSQL (pgvector 计划，本期未启用), Redis, LangGraph (未实装), ARQ (未实装)
- Frontend: React 19, Vite (+@vitejs/plugin-react-swc), TypeScript, Zustand, TanStack Router (file-based, autoCodeSplitting), Tailwind CSS v4, shadcn/ui (Radix UI, style=new-york, baseColor=zinc), `lucide-react`（图标）+ `ldrs`（loader）+ `sonner`（toast）+ `react-hook-form`+`@hookform/resolvers`+`zod`（表单校验）+ `nprogress`（路由进度条）+ `@fontsource/instrument-serif`（self-host 衬线）+ `axios`（请求层）。包管理 npm，dev 端口 7777，走 vite proxy `/api` → 后端 7999。
- shadcn 工作流：组件经 CLI（`npx shadcn@latest add`，**须在 `frontend/` 跑**）/ MCP 添加；新组件用统一包 `radix-ui`，旧手写组件仍用独立 `@radix-ui/react-*`，共存渲染一致。shadcn skill 全局安装（`~/.claude/skills/shadcn`）+ shadcn MCP（仓库根 `.mcp.json`，钉 `--cwd frontend`）已接入。
- Python: 3.13.0（venv 在 `backend/.venv/`，由 uv 管理），Tortoise ORM 1.1.7 内置迁移（`tortoise` CLI 自动读 `pyproject.toml` 的 `[tool.tortoise]`，不引入 aerich）
- API prefix: `/api/v1`（写在 `settings.API_PREFIX`，main.py 通过 `app.include_router(api_router, prefix=settings.API_PREFIX)` 挂载）
- 数据库：复用 DaisyWind 同一个远端 PG 容器，仅 `PG_DATABASE` 不同（本项目 = `cocowork`）

## 当前已有功能
- 后端骨架可启动：`uv run python -m app.main` 跑通 lifespan，FastAPI 接 Tortoise + Redis，中间件 + 异常 + 日志全链路就绪。
- 生产级日志系统：colorlog 开发模式 / JSON 生产模式（按 DEBUG_MODE 切），每条日志带 `[req-xxx]`。
- **User 业务全栈可用**：`users` 表已建（迁移 0001_init_user），三个接口 `/api/v1/users/{register,login,me}` 实测通过。
- **内置 admin 启动自动 seed**（admin / 020121 / is_admin=True，邮箱 nuguri990717@gmail.com）。
- 认证完整：JWT + argon2 哈希，`get_current_user` 每请求查 DB + is_active。
- **前端 User 全栈打通**：登录/注册页（Claude 风双栏 + Instrument Serif + 两张 gopher 错落）→ Zustand auth store → TanStack Router beforeLoad 守卫 → Home 显示 user，端到端实测通过。
- **前端工作台 App Shell（批次1+2）**：`_authenticated` pathless 布局（登录守卫上提，一处保护全部工作台页）+ shadcn sidebar（`floating` 圆角卡片 + `collapsible="icon"` 收起成图标竖条）+ 导航（主页/Agents/知识库/工具/模型）+ footer（设置独立行 + 头像卡片点击下拉，下拉内含退出登录）+ 各模块占位页。admin 入口/独立壳待批次3。

## 下一步
- **前端 App Shell 进行中**：批次1骨架 ✅、批次2（头像菜单+对齐）✅；待办 批次3（admin 独立 `/admin` 壳 + isAdmin 守卫 + 头像下拉加「后台管理」入口）、批次4（Home 卡片式 dashboard）。
- **App Shell 后做 Model + Agent 模块**（本轮敲定的 MVP 第一步；前端先对着类型契约 + mock 搭，再后端填实现）：
  - Model：Provider(凭证，加密落库) / Model(type: chat/embedding/rerank) 两层；统一 OpenAI 兼容客户端（不引 LiteLLM）。
  - Agent：CRUD + 配置表单（模型/system prompt/参数/工具/知识库）+ 配置页内嵌 Playground（调试）；发布后走独立 chat 路由。单 agent 也走 LangGraph（为多 agent 留位）。流式 SSE，前端 assistant-ui 或 Vercel AI Elements。
- **再后做 RAG**：文档处理 → 数据加工（切块/embed/索引）→ 混合检索（向量+FTS+RRF+rerank）。需先启用 pgvector。embedding 先阿里+硅基bge（每库可选）、rerank 先阿里、全文检索先 Postgres 原生 FTS（不够再上 ParadeDB pg_search，不上 ES）、切块默认(递归~512token+50overlap)+可配。
- 后端可选生产功能（RBAC / Email 校验 / 密码重置 / 限流）随需推进。

## 开发注意事项
- 项目 UI 统一使用 `lucide-react`（shadcn/ui 生态默认）作为图标库，`ldrs` 作为 loader 动画，不要引入手写 SVG 或第二套 icon library。
- shadcn 组件用 `npx shadcn@latest add`，**必须在 `frontend/` 目录跑**（components.json 所在）；根 `frontend/tsconfig.json` 已补 `compilerOptions.paths`，否则 CLI 解析不到 `@` 会把组件写进字面量 `frontend/@/`。新组件用统一 `radix-ui` 包。
- `routeTree.gen.ts` 由 TanStack Router 插件自动生成、已 gitignore，不纳入提交。
- 这个 context 文件应该保持紧凑，服务于 AI 快速读取，而不是承担完整项目历史归档。

## 维护规则
- 这个文件只保留当前仍然有效的项目状态。
- 更新时优先重写摘要，不要机械地无限追加内容。
- `最近迭代` 只保留最近 8 次以内的记录。
- 旧的迭代信息应压缩进 `历史摘要`，不要让全文持续变长。
- 如果某次改动不足以影响项目理解，就不要把噪音写进来。

## 最近迭代

### 2026-05-22 — 前端 App Shell（批次1骨架 + 批次2头像菜单）+ shadcn skill/MCP 接入
- 工具链：装 shadcn MCP（仓库根 `.mcp.json`，钉 `--cwd frontend`）+ shadcn skill（全局 `~/.claude/skills/shadcn`，改 `user-invocable: true` 便于手动调）。注意 `skill init` 不是 shadcn 命令，用 `npx skills add shadcn/ui`（skills.sh）装 skill、`npx shadcn@latest mcp init --client claude` 装 MCP。
- 踩坑修复：根 `frontend/tsconfig.json` 缺 `compilerOptions.paths`（paths 只在 tsconfig.app.json），shadcn CLI 解析不到 `@` → 把组件写进字面量 `frontend/@/`；且早先在仓库根跑 mcp init 留下根 `package.json/node_modules` 垃圾。已补根 tsconfig paths（标准修法）、清理全部垃圾。
- 组件约定：保留手写旧组件（独立 `@radix-ui/react-*`）不动；CLI 新组件用统一 `radix-ui` 包（已装），新旧共存、渲染一致。新增 ui 组件：sidebar/sheet/tooltip/separator/skeleton/avatar/dropdown-menu + `hooks/use-mobile`。
- 路由：引入 `routes/_authenticated.tsx` pathless 布局，登录守卫从 `routes/index.tsx` 上提；`/` 等迁入 `_authenticated/`；删 `routes/index.tsx`。占位路由 agents/knowledge/models/tools/settings + `pages/PagePlaceholder`。
- 布局：`components/layout/{AppShell, AppSidebar, UserMenu, nav.config}`。Sidebar `variant="floating"`(圆角卡片) + `collapsible="icon"`(收起成图标竖条)；导航项 `size="lg"` + 放大文字/图标；header logo 用与导航相同 size-5 图标槽以对齐(展开/收起均对齐)。
- footer：设置独立一行 + 头像卡片(UserMenu) 点击弹下拉(顶部用户信息 + 退出登录)；后台管理入口待批次3(/admin 建好后接通)。
- `env.d.ts` 加 `declare module '@fontsource/*'` 修 `noUncheckedSideEffectImports` 的 tsc 报错。
- 自检：tsc -b 退出 0；vite 模块编译通过。
- 决策：sidebar 形态用 shadcn floating + icon-collapsible；点头像=下拉菜单(非直接退出)；设置放下拉外、头像卡片上方；不截图验收(用户自验)；小批次推进、每批用户自行验收。

### 2026-05-22 — 前端从 Vue 3 迁移到 React 19
- 触发：未来 Agent 编排可视化、流式消息、Vercel AI SDK / assistant-ui / ReactFlow 等生态都是 React-first，趁 D1 代码量小（~715 行业务）切换成本最低。
- 技术栈映射：Vue 3 → React 19、Vue Router → TanStack Router (file-based)、Pinia → Zustand、vee-validate → react-hook-form + @hookform/resolvers、vue-sonner → sonner、lucide-vue-next → lucide-react、shadcn-vue (Reka UI) → shadcn/ui (Radix UI)。Tailwind v4 / app.css design tokens / axios 请求层 / ldrs / nprogress / @fontsource/instrument-serif 全部保留不动。
- 路由分两层：`routes/` 只放 TanStack 路由声明 + `beforeLoad` 守卫 + zod search schema，`pages/` 放真正的页面组件，互相清晰解耦。
- Zustand store 形状与 Pinia 对齐：state / getters (() => ...) / actions 三段；组件订阅用 `useAuthStore((s) => s.user)`，beforeLoad 等非 React 上下文用 `useAuthStore.getState()`。
- 注册流改正：后端 `POST /users/register` 实际只返回 `UserOut`（不签 token），原 Vue 版盲存 `undefined` 当 token 是个 pre-existing bug。React 版改为注册成功 → `toast.success('注册成功，请登录')` → `navigate('/login')`，store 不再有 register action。
- shadcn/ui 组件直接手写（不跑 CLI 交互）：button/card/form/input/label/sonner 6 个，全部 new-york + zinc 风格，与 design tokens 自动对齐。
- 老 Vue 版整目录删除，React 项目从 `frontend-react/` 重命名为 `frontend/`，端口回 7777。`.claude/launch.json` 同步更新。
- 实测：登录错误 toast、登录成功跳 Home、刷新后 beforeLoad 补 fetchMe、guestOnly 守卫、404 splat、4 字段 zod 校验全部通过，零 console 报错。
- 决策：路由库选 TanStack Router 而非 React Router v7（类型安全更强 + beforeLoad 守卫天然对应 Vue beforeEach）；状态选 Zustand 而非 Redux Toolkit/Jotai（最轻、心智离 Pinia 最近）；shadcn 不跑 CLI 改为内联手写（避免交互 + 组件量小）。

### 2026-05-21 — 前端从零搭建 + User 全栈打通（A7/A8 + C1-C3/C6 + D1 前端）
- 脚手架（A7）：Vite + Vue3 + TS + Pinia + Router + ESLint/Prettier/oxlint，结构参照 DaisyWind 但精简（删 D2/D3 的 milkdown/mermaid/highlight 等依赖）；端口 7777，vite proxy `/api`→7999（沿用 DaisyWind 开发套路）。
- 样式系统（A8）：Tailwind v4 CSS-config + shadcn-vue（new-york/zinc，单主题不切换，但保留 .dark tokens 预留）；加 `--color-brand:#2f6b53`（流式/品牌专用）+ success/warning 语义色；nprogress 进度条走 brand 色。
- types（C8）：`types/api.ts`(ResponseModel/PageData) + `types/user.ts` + barrel，对齐后端 schema（决定抽 types 而非 DaisyWind 的 inline 风）。
- request（C1）：axios 拦截器**解包到 data**（调用方直接拿 T）+ `ApiBusinessError` Error 实例 + `silent` 双轨 toast（声明式，替代 DaisyWind 硬编码路径）+ 401 防循环登出；删掉 DaisyWind 的 loading-Ref 参数（UI 状态归组件）。
- auth（C3）：Pinia composition store（token 持久化 localStorage，user 不持久化）+ `api/auth.ts`。
- router（C2）：`meta.requiresAuth/guestOnly` 守卫 + 刷新后 `fetchMe` 保活 + `?redirect=` 跳回。
- 组件（C6）：shadcn-vue add button/input/label/form/sonner/card + vee-validate+zod 校验。
- 登录注册（D1 前端 + C9）：`AuthShell` 双栏（Claude 版式 + shadcn zinc 配色）+ Instrument Serif 大标题 + 两张 gopher（dao + fcb-glass）错落叠放 + zod 字段校验 + 业务错误 toast。admin 端到端实测通过。
- 决策：图标库 phosphor→**lucide-vue-next**（shadcn 生态默认）；字体 **self-host @fontsource**（避 Google CDN 被墙 + 消 FOUT）；**主题切换不做**；登录页只学 Claude 版式、配色用 shadcn 默认；layout/sidebar(C4)/composables(C5)/common(C7) **暂缓**（等登录后页面方向想清楚）。

### 2026-05-20 — D1 User 业务全栈完成 + 首次迁移 + admin seeding
- User 模型：UUID7 单主键（`UUIDBaseModel`）+ `TimestampMixin`；username/email 唯一、password_hash、nick_name、avatar_url、is_active/is_admin。表名 `users`（复数，避开 PG 保留字 user）。
- Schema：UserRegister/UserLogin/UserOut/TokenOut；EmailStr 校验、username 限字母数字下划线、password ≥6（从 8 降到 6 以兼容 admin 弱密码 020121）、nick_name ≥2 必填。
- Service（类风格，自带 `get_user_service` provider）：register 双唯一校验 + IntegrityError 兜底；authenticate 用户名枚举防御（统一错误消息）；login 签 token。密码哈希在 service 调 security，不耦合 model。
- 路由 `/register /login /me`：采纳 fastapi skill 推荐 —— Annotated 依赖别名、`-> ResponseModel[T]` 返回类型（走 Pydantic Rust 序列化）、prefix 写在 router 自身。
- depends.py 追加 `get_current_user`：基于 `get_current_token_payload` 二次组合，每请求查 DB + is_active（封禁即时生效）。
- success/page 改返 ResponseModel 实例（配合返回类型）。
- 迁移：`tortoise init` + `makemigrations -n init_user` + `migrate`，0001_init_user 建 users 表。注意：模型要在 `app/models/__init__.py` re-export，否则 Tortoise 检测不到（"No changes detected" 坑）。
- admin seeding：方案 A（独立脚本）+ 方案 B（lifespan 自动）合一，幂等 + IntegrityError 并发安全；密码定死 020121，邮箱 nuguri990717@gmail.com（注意 EmailStr 拒绝 `.local` 等保留 TLD）。
- 决策：User 主键 UUID7 单主键（不用 BigInt+UUID 双 ID）；密码哈希放 service 不放 model；is_active+is_admin 保留（RBAC 留待专门一轮）。

### 2026-05-20 — Phase 2 后端通用模块全部完成（B2–B7 + 日志系统）
- B2 Redis 客户端 + lifespan 接入。
- B3 异常体系：5 个业务异常类 + 4 个 handler，统一 `{code, message, data}` 响应壳（沿用 DaisyWind "全 200" 风格）。
- B4 中间件：AccessLog + CORS；后续日志任务追加了 RequestIDMiddleware（纯 ASGI 实现规避 contextvar 跨 Task 丢失）。
- B5 统一响应壳：ResponseModel[T] / PageData[T] + success/page 函数；删掉了 DaisyWind 的 `error()` 反模式。
- B6 安全：argon2 主推 + bcrypt 兼容，`verify_token` 失败抛 `AppAuthenticationFailed`（不再返回 None），token 加 `iat` claim。
- B7 认证依赖薄层：`bearer_scheme` + `get_current_token_payload`；User 实体加载 (`get_current_user`) 推迟到 D1 完成 User 模型后再加。
- 中途插入：生产级日志系统（colorlog + python-json-logger，按 `DEBUG_MODE` 切换文本/JSON，RequestIDFilter 把 request_id 注入每条日志，接管 uvicorn 三个 logger，压低 9 个第三方库到 WARNING）。
- 中途插入：`app/core/` 重组成子包（`exceptions/`、`http/`、`logging/`），避免 11 文件平铺。
- 决策：分页字段沿用 DaisyWind 中式命名（records / current_page）；HTTP 状态码策略沿用 DaisyWind "全 200" 风格（与生产级 REST 偏好不同，按用户决策保留）。

### 2026-05-19 — Phase 1 后端骨架完成
- 决策：本轮范围 A+B+C+D1（骨架 + 后端通用 + 前端通用 + User 全栈）；Agent 框架锁定 LangGraph；复用 DaisyWind 远端 PG 容器新建 database `cocowork`；迁移用 Tortoise 1.x 内置（不引 aerich）；Python 3.13；API 前缀 `/api/v1` 单层路由组。
- 落盘：`backend/pyproject.toml`、`.env.example`、`app/{__init__,main}.py`、`app/{api,core,db,models}/__init__.py`、`core/config.py`、`db/postgresql.py`、`api/__init__.py`、`migrations/README.md`、`tests/__init__.py`；顶层 `.gitignore` 加 `.DS_Store`。
- 偏差：`main.py` 暂未接 Redis/异常/中间件（待 B2/B3/B4）；`pyproject.toml` 多加 `boto3` + `tavily-python`（后续会用），但 `.env.example`/`config.py` 暂不放 R2/Tavily 字段避免配置-代码不同步。
- 跑通验证：服务在 `127.0.0.1:7999` 成功启动，Tortoise 初始化无错。

## 历史摘要
（暂无）

## 后续使用方式
- 每次开启新的 AI 对话时，先读取这个文件。
- 每次完成有意义的开发后，更新这个文件一次。
- 可以直接用类似 `更新 context`、`把这次改动写入 context`、`压缩 context` 的指令触发维护。
