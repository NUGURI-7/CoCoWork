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

## 技术栈
- Backend: FastAPI, Tortoise ORM, PostgreSQL (pgvector 计划，本期未启用), Redis, LangGraph (未实装), ARQ (未实装)
- Frontend: React 19, Vite (+@vitejs/plugin-react-swc), TypeScript, Zustand, TanStack Router (file-based, autoCodeSplitting), Tailwind CSS v4, shadcn/ui (Radix UI, style=new-york, baseColor=zinc), `lucide-react`（图标）+ `ldrs`（loader）+ `sonner`（toast）+ `react-hook-form`+`@hookform/resolvers`+`zod`（表单校验）+ `nprogress`（路由进度条）+ `@fontsource/instrument-serif`（self-host 衬线）+ `axios`（请求层）。包管理 npm，dev 端口 7777，走 vite proxy `/api` → 后端 7999。
- Python: 3.13.0（venv 在 `backend/.venv/`，由 uv 管理），Tortoise ORM 1.1.7 内置迁移（`tortoise` CLI 自动读 `pyproject.toml` 的 `[tool.tortoise]`，不引入 aerich）
- API prefix: `/api/v1`（写在 `settings.API_PREFIX`，main.py 通过 `app.include_router(api_router, prefix=settings.API_PREFIX)` 挂载）
- 数据库：复用 DaisyWind 同一个远端 PG 容器，仅 `PG_DATABASE` 不同（本项目 = `cocowork`）

## 当前已有功能
- 后端骨架可启动：`uv run python -m app.main` 跑通 lifespan，FastAPI 接 Tortoise + Redis，中间件 + 异常 + 日志全链路就绪。
- 生产级日志系统：colorlog 开发模式 / JSON 生产模式（按 DEBUG_MODE 切），每条日志带 `[req-xxx]`。
- **User 业务全栈可用**：`users` 表已建（迁移 0001_init_user），三个接口 `/api/v1/users/{register,login,me}` 实测通过。
- **内置 admin 启动自动 seed**（admin / 020121 / is_admin=True，邮箱 nuguri990717@gmail.com）。
- 认证完整：JWT + argon2 哈希，`get_current_user` 每请求查 DB + is_active。
- **前端 User 全栈打通**：登录/注册页（Claude 风双栏 + Instrument Serif + 两张 gopher 错落）→ Zustand auth store → TanStack Router beforeLoad 守卫 → Home 显示 user，浏览器端到端实测通过（含 zod 字段校验 / 业务错误 toast / 刷新保活 / 退出 / 404 / 注册成功跳登录）。

## 下一步
- **前端：登录后的产品内页方向待定**（sidebar 传统软件式 vs 其他形态，用户还没想好）→ 想清楚再做 layout / hooks / common 组件。React 生态可选：TanStack Query（数据获取/缓存）、@tanstack/react-table（数据表）、ReactFlow（Agent 编排可视化）、assistant-ui 或 Vercel AI SDK（聊天流式）。
- 后端方向（可选）：D2/D3 更多业务模块；或 RBAC / Email 校验 / 密码重置 / 限流等生产功能；或将 `/users/register` 也返回 token 让注册自动登录（当前是注册成功跳登录页）。
- Agent 平台核心（远期）：LangGraph 接入、ARQ 任务队列、pgvector RAG。
- 具体走哪个方向待定，下次对话开始时再选。

## 开发注意事项
- 项目 UI 统一使用 `lucide-react`（shadcn/ui 生态默认）作为图标库，`ldrs` 作为 loader 动画，不要引入手写 SVG 或第二套 icon library。
- 这个 context 文件应该保持紧凑，服务于 AI 快速读取，而不是承担完整项目历史归档。

## 维护规则
- 这个文件只保留当前仍然有效的项目状态。
- 更新时优先重写摘要，不要机械地无限追加内容。
- `最近迭代` 只保留最近 8 次以内的记录。
- 旧的迭代信息应压缩进 `历史摘要`，不要让全文持续变长。
- 如果某次改动不足以影响项目理解，就不要把噪音写进来。

## 最近迭代

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
- 决策：
  - 本轮范围 A+B+C+D1（骨架 + 后端通用 + 前端通用 + User 全栈），本次提交完成 A。
  - Agent 框架锁定 LangGraph，不从 DaisyWind 拷 `pydantic-ai` / `agents/` / `tools/` / `ingestion/`。
  - 复用 DaisyWind 远端 PG 容器，新建 database `cocowork`。
  - 迁移工具：Tortoise 1.x 内置（不引入 aerich，DaisyWind 那个 `aerich.ini` 是历史残留）。
  - Python 3.13 路线（容忍未来 Docker 也用 3.13）。
  - API 前缀 `/api/v1`，路由组单层（不像 DaisyWind 套两层）。
  - 测试基础设施先建（pytest 配置已就位）但 `conftest.py` 推迟到 D1 写 User 时连同第一个测试一起写，避免空 fixture 死代码。
- 落盘：
  - `backend/pyproject.toml`、`backend/.env.example`、`backend/app/{__init__,main}.py`、
    `backend/app/{api,core,db,models}/__init__.py`、`backend/app/core/config.py`、
    `backend/app/db/postgresql.py`、`backend/app/api/__init__.py`、
    `backend/migrations/README.md`、`backend/tests/__init__.py`。
  - 顶层 `.gitignore` 加了 `.DS_Store`。
- 与原 Phase 1 spec 的偏差：
  - `main.py` 暂未接 Redis / 异常处理器 / 中间件（依赖 B2/B3/B4 模块未到位），Phase 2 写完对应模块后回头补 4–6 行 import + register。
  - `pyproject.toml` 比最初规划多加了 `boto3` + `tavily-python`（用户确认后续会用）。但 `.env.example` 与 `config.py` 暂不放 R2 / Tavily 字段，等 E 阶段实装时再加，避免配置-代码不同步。
- 跑通验证：服务在 `127.0.0.1:7999`（或 .env 配的端口）成功启动，Tortoise 初始化无错。

## 历史摘要
（暂无）

## 后续使用方式
- 每次开启新的 AI 对话时，先读取这个文件。
- 每次完成有意义的开发后，更新这个文件一次。
- 可以直接用类似 `更新 context`、`把这次改动写入 context`、`压缩 context` 的指令触发维护。
