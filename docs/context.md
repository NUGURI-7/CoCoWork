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
- Backend: FastAPI, Tortoise ORM, PostgreSQL (pgvector 0.8.1 已启用), Redis, LangGraph (未实装), ARQ (未实装)
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
- **Model 模块后端完成**：Provider（供应商凭证）+ AIModel（模型实例，支持覆盖 Provider 的 base_url/api_key）+ ProviderModelCatalog（管理员维护的可用模型目录）三层数据模型；Fernet 加密存储 API Key；Validator 策略模式（按 provider_type + model_type 二维查找）在创建/更新时验证连通性；统一 OpenAI 兼容客户端（ModelClient）；参数定义端点（动态表单元数据）。**AIModel URL 已 nested 化**：`/providers/{pid}/models/*`（5 个 CRUD）+ 保留 flat `/models`（跨 provider 查询）+ `/models/param-definitions`（静态元数据）。
- **前端 User 全栈打通**：登录/注册页（Claude 风双栏 + Instrument Serif + 两张 gopher 错落）→ Zustand auth store → TanStack Router beforeLoad 守卫 → Home 显示 user，端到端实测通过。
- **前端工作台 App Shell（批次1+2）**：`_authenticated` pathless 布局（登录守卫上提，一处保护全部工作台页）+ shadcn sidebar（`floating` 圆角卡片 + `collapsible="icon"` 收起成图标竖条）+ 导航（主页/Agents/知识库/工具/模型）+ footer（设置独立行 + 头像卡片点击下拉，下拉内含退出登录）+ 各模块占位页。admin 入口/独立壳待批次3。
- **前端 Model 模块全栈打通**：Provider/AIModel 的创建 + 删除（不做编辑，改配置=重建）+ Catalog 查询展示 + 参数动态表单，全部对接后端 API。`api/model.ts` 统一封装三层接口；删除走 AlertDialog 二次确认；列表 loading 用 ldrs `l-ring`（品牌色 `#2f6b53`、60vh 居中）替代 skeleton。
- **前端 admin 后台分区**：`/admin` 独立壳（AdminShell/AdminSidebar/admin-nav + isAdmin 守卫 + 独立 tab 系统），头像下拉「后台管理」入口。系统设置用「左侧二级导航 + 右侧内容」（仿 Claude settings），首个设置项 = **模型目录管理**（Catalog 表格增删，admin 写入），admin 不再需要手调接口喂数据。
- **前端工具模块占位页（静态 mock）**：`/tools` 三带式（Header / 统计带 / Tab）+ 按来源 tab（全部/内置/MCP）+ 卡片网格 + 单卡启用开关。后端 tool/skill 暂缓，纯前端骨架。
- **前端知识库模块 CRUD 接通**：库级 list/get/create/update/delete 全对接后端 `/knowledge-bases`；列表页卡片网格 + 详情页（库信息 header + 文档/检索测试/设置 三 tab）；删除入口双处（卡片三点 + 设置页），成功后自动关闭对应 workspace tab。文档列表/上传弹窗/检索测试 tab 仍 mock，等后端片4/片6。
- **后端存储抽象层就位**：`app/core/storage/`（`Storage` ABC + R2/Local 双实现 + 按 `STORAGE_BACKEND` 装配的模块级单例 `storage`）；R2 支持预签名直传/下载、Local 走后端中转 + 路径穿越防护；同步 IO 全包 `asyncio.to_thread`、boto3 client 懒加载。
- **知识库 Document 数据层就绪（4b-1）**：`DocumentService`（create_pending / list_by_kb / get_by_id / delete）+ 扩展名白名单 md/txt + 大小上限 50MB + storage 对象联动清理（删失败仅 log 不阻塞）；schemas 含 `UploadInitOut` 带 strategy 字段为 4b-2 端点分流预埋。**无路由，4b-2 才接端点**。

## 下一步
- **当前优先 = 知识库 / RAG 模块**（独立于 Agent / 对话，是更硬的基础设施，优先级上调）。前端**库级 CRUD 全接通**（列表/详情/新建/保存/删除，见最近迭代）；前端待办：文档列表/上传弹窗（mock 中，待片4）、检索测试页（待片6）。
  - **后端方案已定稿**：见 `docs/design/knowledge-rag-v1.md`（spec + §13 实施切片清单）+ `knowledge-rag-decisions.md`（决策/权衡）。按 §13 切 6 片小步推进：**片1+2+3 + 4a + 4b-1 已完成**（VectorField + pgvector + 4 表迁移 0005 + AIModel.meta 迁移 0006 + 知识库 CRUD `/api/v1/knowledge-bases` 5 端点 + 存储抽象层 R2/Local 双后端 + Document schemas/service）；**片4b 剩**：4b-2 上传端点（R2 三段式 presign→PUT→confirm + Local passthrough multipart 分流，`upload-init` 自带 strategy 字段）+ 4b-3 列表/删除/下载链接 → 片5 处理管线 → 片6 检索+命中测试。详见最近迭代。
  - 既有决策：embedding 每库锁一个模型、rerank 先阿里、全文检索先 Postgres 原生 FTS（不够再上 ParadeDB pg_search，不上 ES）、切块默认（递归~512token+50overlap）+ 可配；混合检索/FTS/RRF/rerank/多向量 = v2；文档编辑用自封装 tiptap（后做）。
- **Agent 模块（搁置，优先级下调）**：详情页布局已定 = **左配置 + 右 Playground 双栏**；配置栏 MVP 字段顺序 ①基础(名称/描述) ②模型(下拉选已建 chat 模型) ③System Prompt(大文本框) ④调用参数(滑块,折叠) ⑤知识库[+关联] ⑥工具[+关联]，其中 ⑤⑥先占位禁用、功能后置；Playground 用草稿配置实时调试。单 agent 也走 LangGraph（为多 agent 留位）；流式 SSE，前端 assistant-ui / Vercel AI Elements。后端 Agent 模型 + LangGraph 均未建。
- **前端 App Shell**：批次1骨架 ✅、批次2 头像菜单 ✅、批次3 admin 独立壳 ✅、批次4 Home 卡片式 dashboard ✅（静态占位版，数字待各模块接口就绪后灌真数）。
- 后端可选生产功能（RBAC / Email 校验 / 密码重置 / 限流）随需推进。

## 开发注意事项
- 项目 UI 统一使用 `lucide-react`（shadcn/ui 生态默认）作为图标库，`ldrs` 作为 loader 动画，不要引入手写 SVG 或第二套 icon library。
- **品牌色（`#2f6b53`）走「路线 C 适度品牌化」**：主色 `--primary` 保持中性（zinc 黑），品牌色只铺导航/选中/强调等非语义场景。已在 `app.css` 建一套色阶 token（`--brand` base 精确 hex + `color-mix` 派生 `-foreground`/`-hover`/`-subtle`/`-border`，light+dark 各一套），注册成工具类 `bg-brand`/`text-brand`/`bg-brand-subtle`/`border-brand-border`/`hover:bg-brand-hover`。**用色约定：激活/选中态 = `bg-brand-subtle`+`text-brand`，hover 保持中性灰；成功/警告/危险仍走 `success`/`warning`/`destructive`，勿与品牌绿混用；别再手写 `bg-brand/8` 这类透明度，用色阶 token。** 改 base 只需动 `:root` 的 `--brand` 一处，整套跟着变。
- **可点卡片统一加 `card-interactive`**（`app.css` 的 `@utility`）：封装品牌化 hover = 边框转墨绿实色 + 淡墨绿柔光阴影 + 上浮 1px。所有可点击的 Card 用它，别再各写 `hover:shadow-md` / `ring` 等零散 hover；展示型卡片（登录表单、详情信息卡）不加。
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

### 2026-05-26 — 知识库/RAG 后端：4b-1 Document schemas + service

- **4b-1 完成**：Document 数据层平地起步，模型早在迁移 0005，不动表/迁移。
- 新增 `schemas/knowledge/document_schema.py`：`DocumentOut` + `UploadInitIn` + `UploadInitOut`（带 `strategy: "presign"|"passthrough"` 字段，4b-2 端点按存储后端分流用）+ 常量 `ALLOWED_FILE_TYPES = {"md","txt"}`（放代码、不入 env——产品/业务边界，部署者不该随手放宽）。
- 新增 `services/knowledge/document_service.py`：`DocumentService`（class 风格对齐 KB service）+ helper `_parse_file_type`/`_build_storage_key`。方法 `create_pending` / `list_by_kb` / `get_by_id` / `delete`，全 nested 签名 `(user, kb_id, ...)`，doc_id 永远在 kb_id 之后（URL 同步 nested 化）。
- `storage_key` 约定 `kb/{kb_id}/doc/{doc_id}.{ext}`，两后端通用；含 doc_id 故 create 占位 → 拿 id → update 回填（两次写但顺现有风格）。
- 删文档：先 `storage.delete`（失败仅 log 不阻塞）→ ORM delete（FK CASCADE 自动清 paragraphs/embeddings）。理由：用户始终能清掉 ORM 记录，孤儿对象交给桶生命周期。
- 归属校验：`_get_user_doc` 一次 SQL JOIN 同时验「doc 在 kb 下 + kb 归属当前用户」（filter 走 FK 路径 `knowledge_base__created_by=user`，不用 select_related——前者是"我要用字段"，后者是"我只过滤"）。
- config 加 `STORAGE_MAX_UPLOAD_SIZE = 50MB`（env 可调）；扩展名白名单不入 env。
- 不含路由（4b-2 才接端点）；端点设计：`upload-init` 自带 `strategy` 字段按 backend 分流（R2 presign 三段式 / Local passthrough 一步），前端按 strategy switch、不用提前问能力。

### 2026-05-26 — Model 模块：AIModel URL nested 化（/providers/{pid}/models）

- 后端路由 `ai_model.py` 拆 `nested_router`（`/providers/{pid}/models`，5 个 CRUD）+ `flat_router`（保留 `/models` 跨 provider 列表 + `/models/param-definitions`）；`model/__init__.py` 注册两个 router。
- 拍板保留 `GET /models?model_type=...`：建 KB 选 embedding 模型场景需要跨 provider 列出，强制 nested 会让前端 N+1（先 listProviders 再每个 provider 调一次），不值。
- `ModelCreate` 删 `provider_id` 字段：path 单源、避免 path/body 双源歧义（万一 path 是 abc 但 body 是 def，听谁都是坑）。
- `AIModelService` 加 `_ensure_user_provider` helper；按 provider 的方法签名都带 pid；`list_own` 一分为二：`list_by_provider`（nested 端点用，强校验 pid 归属）+ `list_own`（跨 provider 列出，只过滤 user）。
- 前端 `api/model.ts`：`listModels` 拆 `listModelsByProvider` + `listAllModels`；`createModel(providerId, payload)` / `deleteModel(providerId, modelId)` 多 pid 参数；`ModelCreatePayload` 去 `provider_id`。
- 前端 4 个调用点适配：`CreateModelDialog`（payload 去 provider_id 改单独传）/ `AIModelCard`（props 加 providerId）/ `ProviderDetailPage`（调 listModelsByProvider + 给 AIModelCard 传 providerId）/ `CreateKnowledgeDialog`（调 listAllModels）。`tsc --noEmit` 0 报错。
- 决策对齐：现有 KB/Provider/Catalog 已 flat（顶层无父），nested 只用于真正的父子关系（KB→Document / Provider→AIModel）；纯静态资源（param-definitions）不强求 nested。

### 2026-05-25 — 知识库/RAG 后端：4a 存储抽象层（R2 预签名 + Local 中转）

- **4a 完成**：`app/core/storage/` 抽象基类 + R2/Local 双后端 + `STORAGE_BACKEND` env 装配。业务用法 `from app.core.storage import storage; await storage.save(...)`，后端类型透明。
- 文件：`base.py`（4 字节操作 `save/read/delete/exists` + 2 预签名方法 + `supports_presigned` 标志）/ `local.py`（`shutil.copyfileobj` 流式拷贝 + 路径穿越防护）/ `r2.py`（boto3 + `to_thread` + 客户端 `@cached_property` 懒加载）/ `__init__.py`（按 env 装配单例）。配套：`config.py` 加 `STORAGE_BACKEND` + R2 4 字段（去掉 `R2_PUBLIC_URL`，YAGNI）；`.env.example` 同步；`.gitignore` 加 `backend/data/`。
- **上传/下载选型（实施时定，不对称）**：**R2 走预签名直传**（客户端→R2 直连，**服务器零出站**）+ 下载走预签名 GET URL；**Local 走后端中转**（本地盘没"直传 URL"概念）。接口用 `supports_presigned: bool` 标志 + 基类抛 `NotImplementedError` 默认实现表达；业务层按标志分流上传路径。
- **关键洞察（戳破认知坑）**：「RAG 反正要处理拉回来 → presigned 省上传带宽有限」**错**——服务器**出站(egress)收费 / 入站(ingress)免费**；passthrough 上传的「后端→R2」是出站，presigned 直接绕开，**入站和出站不对称、presigned 省的是真金白银**。详 `knowledge-rag-decisions.md` §8c + `notes/backend/storage-upload/notes.md`。
- 工程点：boto3 client **`@cached_property` 懒加载**——import/启动不依赖 R2 凭证（修了"空 endpoint 启动崩"的真问题）；同步 IO 全包 `asyncio.to_thread`（预签名生成不包，纯本地 HMAC）；大文件靠 `UploadFile` 1MB spool + `shutil.copyfileobj` 64KB 分块拷贝，几十兆不爆内存。
- 验收：local smoke 全过（save→exists→read→delete + 路径穿越拦截 + 预签名拒抛 `NotImplementedError`）；R2 smoke 等 `backend/.env` 填真凭证后跑或前端集成时验。
- 配套：§13 把片4 拆 **4a✓ + 4b 待办**；新增 `notes/backend/storage-upload/{notes.md, qa.md}`（4 节原理 + 2 问答）；决策 §8c 入 `knowledge-rag-decisions.md`。
- 协作偏好新增：notes/ 学习笔记**在模块/切片做完后统一批量写**，不在实现途中写（已记进 MEMORY）。

### 2026-05-25 — 知识库前端：设置页保存/删除接通 + 卡片删除入口
- **设置 tab 接真接口**：`KnowledgeSettings` 保存改 `updateKnowledgeBase`（silent，失败自行 toast），删除改 `deleteKnowledgeBase` + `close('/knowledge/'+id)` 关详情标签 + 跳回列表。新增 `onUpdated` 回调，详情页 `setKb` 同步 header。
- **卡片加删除入口**：`KnowledgeCard` 仿 ProviderCard 加三点 dropdown + AlertDialog；列表页传 `onDeleted={refetch}`；删除同样关详情标签。删除入口两处（卡片三点 + 设置页），跟供应商对齐。
- **`deleteKnowledgeBase` 去 silent**：跟 model 模块删除约定（失败走拦截器 toast）统一；之前是写 api 时跟着 create/update 一起被顺手加的。
- **ProviderCard 补关标签**：之前漏的，`handleDelete` 成功后 `close('/models/'+id)`。
- 决策：设置页只允许改 name/description，向量化配置（embedding 模型/chunk_config）锁死只读；删除关 tab + 跳回列表，避免标签残留死链。

### 2026-05-25 — 知识库/RAG 后端：片3 CRUD + Model 模块顺手补 dim 探测

- **片3 完成**：`/api/v1/knowledge-bases` 5 端点（POST/GET 列表/GET 详情/PUT/DELETE），鉴权 + 用户级可见。文件 `schemas/services/api/routes/knowledge/`（镜像 model 模块三层结构）。
- 分层选择：**service 直接返回组装好的 `KnowledgeBaseOut`** 而非 ORM——因为 Out 含跨实体计算字段（embedding 模型名 + 文档/子块计数），model_validate 装不下；route 极薄、纯透传。
- **Model 模块顺手改（A1–A4）**：`validator.validate` 签名从 `-> None` 改成 `-> dict[str, Any]`；embedding 子类把现有校验请求的响应向量长度 `len(resp.data[0].embedding)` 当作 `{"embedding_dim": N}` 返回；`AIModelService.create` 写入 `AIModel.meta`。**零额外上游调用**——dim 在建模型那一刻就落库。`ModelOut` 加 `meta` 字段对外暴露。
- 建库 dim 解析：先读 `model.meta["embedding_dim"]`，缺失才走 `_probe_embedding_dim` 兜底（针对老模型，调用 `ModelClient.create_embedding(model, ["x"])` 取 len 并回写 meta）。
- 计数实现：`annotate(Count("documents", distinct=True), Sum("documents__chunk_count"))`。**踩坑**：select_related + annotate 同用 → 被 join 的 FK 列（`embedding_model.display_name`）不进 GROUP BY → Postgres 报「must appear in the GROUP BY clause」。**解法**：annotate-only 查计数 + 模型名单独 `AIModel.filter(id__in=...).values_list("id","display_name")` 批量查（无 N+1）。
- 决策：不许换 embedding 模型（换模型 = 全库重建，归 reindexing）；update 只允许 name/description/chunk_config；删库靠 FK CASCADE 自动清文档/段/向量。
- 验收：smoke 跑通（5 路由注册、annotate 查询执行）。旧 embedding 模型 `meta` 为空也能用——建库探测兜底会补；想干净可删后重建。
- 前端 KB 静态页此前已有，待另起会话接 API。

### 2026-05-24 — 知识库/RAG 后端：设计定稿 + 数据层（片1+2）+ AIModel.meta
- 设计文档定稿：`docs/design/knowledge-rag-v1.md`（spec + §13 切片清单）+ `knowledge-rag-decisions.md`（决策/权衡）；通用学习笔记 `notes/backend/`（4 模块，已 gitignore 不入库）。
- 模型决策：4 表 `knowledge_bases`/`documents`/`paragraphs`/`embeddings`（全在 `app/models/knowledge.py` **单文件**）。父子块：embed 小子块、命中返回**整段**；**子块不落表**，文本存 `embedding.text`；Embedding 独立成表（一对多指回段 + `source_type` content/question/title，多向量留口子，v1 只 content）；Embedding 不可变、只 `created_at` 无 `updated_at`。
- pgvector：容器原无、已装 **0.8.1**（PG 18）。Tortoise 无原生支持 → 自定义 `app/db/fields.py:VectorField`（`SQL_TYPE="vector"` **不锁维度**、list↔文本转换；相似度查询走原生 SQL `embedding::vector(dims) <=>`，按段去重 `DISTINCT ON`）。ANN 索引按知识库建**部分索引** + `embedding::vector(dims)` 表达式 cast（参考 MaxKB；查询 cast/过滤须与索引一致才命中），v1 量小先 seq scan；>2000 维 HNSW 不支持（halfvec/降维）。
- 存储：抽象 + 双后端（本地默认 / S3 兼容 R2，启动按 `STORAGE_BACKEND` 选）——**延后到片4 上传时再写**（不硬绑 R2，自托管可用本地盘、零基建不走网络）。v1 **手动向量化**（上传只建 pending、手动触发，逻辑收在 `process_document()`，FastAPI BackgroundTasks 跑；将来换 ARQ 不返工）。
- 进度：片1 ✅ VectorField；片2 ✅ 迁移 0005 已 apply，4 表建好、`embeddings.embedding` 列 = vector（迁移头部 RunSQL `CREATE EXTENSION IF NOT EXISTS vector`）。
- AIModel 加 `meta` JSONField（**`null=True`**，存 dim/context_window 等「模型固有事实」，区别于用户可调的 `config`；前端 Model 卡片将展示）。建库取 `embedding_dim` 用**懒填充**：首次用到该 embedding 模型时实测 embed 拿 dim 回写 `AIModel.meta`。**迁移 0006 待跑**：旧 0006（meta NOT NULL）因已有行报 NotNullViolation → 已删旧文件、模型改 `null=True`；下一步 `uv run tortoise makemigrations -n add_aimodel_meta` 重生成 → 审 → `migrate`。
- 协作约定：**小步！一次只写一小块、等用户确认再继续**；迁移先 `makemigrations` 给用户审、**由用户跑 `migrate`**；代码读 meta 兜底 `(m.meta or {})`。

### 2026-05-24 — 知识库列表页 + 详情页前端（静态 mock）+ 模块 IA 决策
- `/knowledge` 落地静态版：**三带布局**（Header / 概览统计带 / 卡片网格 + 虚线新建卡）；左侧目录树 `KnowledgeFolderTree` 现 `return null`，但外层已是两栏 flex —— **将来加文件夹树只需填左栏、不推翻**。
- 文件：`pages/knowledge/{KnowledgePage,KnowledgeCard,KnowledgeFolderTree,mock.ts}`，路由由占位换成 `KnowledgePage`。
- IA/展示决策：库列表用**卡片网格**、文档详情用**列表行**（两层不同形态，避免同质化）；文件夹归类**知识库**（左树，后做），库内文档**平铺**；单卡 = 墨绿图标块 + 状态点(success/warning/destructive) + 分隔线 + 大数字(文档/chunks) + embedding badge，复用 `card-interactive`。
- 数据形状预埋 `KnowledgeBase{id,name,description,doc_count,chunk_count,embedding_model,status,updated_at}`；未接 API，新建按钮占位。
- 详情页 `/knowledge/$kbId`：面包屑 + 库信息 header + shadcn `tabs`（文档/检索测试/设置）；「文档」tab = **列表行**（`DocumentList`，含状态徽标），检索测试/设置先占位空态。路由照 models 重构（`knowledge.tsx`→Outlet 布局 + `knowledge/{index,$kbId}.tsx`），装 shadcn `tabs`，列表卡片点击→详情。决策：详情页**不做独立专属 sidebar**（产品体量小）改用 tab；分段管理下钻到文档、问题管理后置。`KnowledgeDoc{id,kb_id,name,type,size,chunk_count,status,uploaded_at}`，`statusMeta` 状态徽标 KnowledgeCard/DocumentList 共用。

## 历史摘要
- **2026-05-23 — Model 模块全栈打通（后端+前端+admin Catalog 管理）**：后端 3 表数据层 Provider/AIModel/ProviderModelCatalog（迁移 0002-0004）+ Fernet 加密 + Validator 策略模式（按 `(provider_type, model_type)` 二维查找）+ 统一 ModelClient（凭证 Model 级 > Provider 级回退）；前端 CRUD 闭环（loader 用 ldrs `l-ring` 品牌色 60vh 居中替代 skeleton，删除统一 AlertDialog，不做编辑）；admin 系统设置二级导航 + Catalog 表格管理（admin 不用手调接口喂数据）。决策细节见 git log（210f620/cf37beb）；后续 5-26 URL nested 化时调整。
- **2026-05-22 — 前端 Vue→React 19 迁移 + App Shell 批次1+2 + shadcn skill/MCP 接入**：触发=Agent 流式/编排生态 React-first（趁 D1 代码量小切换）；映射 Vue→React 19 / Vue Router→TanStack Router (file-based) / Pinia→Zustand / shadcn-vue→shadcn/ui (Radix UI)；App Shell 跑出 `_authenticated` 守卫 + floating sidebar (collapsible="icon") + UserMenu 头像下拉 + 各模块占位页骨架；shadcn skill+MCP（仓库根 `.mcp.json` 钉 `--cwd frontend`）接入。详细决策见 git log。
- **2026-05-21 — 前端从零搭建（Vue3 版）+ User 全栈对接**：Vite+Vue3+Pinia+shadcn-vue 脚手架、axios 拦截器（`ApiBusinessError` + `silent` 双轨 toast）、router 守卫（`requiresAuth`/`guestOnly` + `fetchMe` 保活）、登录/注册页（AuthShell 双栏 + Instrument Serif + zod 校验）。**后被 05-22 React 迁移完全替换**，技术栈细节见当时迭代。
- **2026-05-20 — D1 User 全栈 + 首次迁移 + admin seeding**：User 模型(UUID7+TimestampMixin、`users` 表)、register/login/me（Annotated 依赖 + `-> ResponseModel[T]`）、`get_current_user` 每请求查 DB+is_active、迁移 0001、admin lifespan 幂等 seed（020121）。坑：模型要在 `app/models/__init__.py` re-export 否则 Tortoise 检测不到。
- **2026-05-20 — Phase 2 后端通用模块（B2–B7 + 日志）**：Redis + lifespan、异常体系（5 类 + 4 handler + 全 200 壳）、中间件（AccessLog/CORS/RequestID 纯 ASGI）、`ResponseModel[T]`/`PageData[T]`、安全（argon2+bcrypt、token 加 iat）、认证依赖薄层、生产级日志（colorlog/JSON 按 DEBUG_MODE 切 + RequestIDFilter）；`core/` 重组成 exceptions/http/logging 子包。决策：分页中式命名、HTTP 全 200 风格。
- **2026-05-19 — Phase 1 后端骨架**：搭出 `backend/` 基础结构（pyproject/uv、config、db/postgresql、api 路由组）；锁定 Agent 框架 = LangGraph、迁移 = Tortoise 1.x 内置（不引 aerich）、Python 3.13、API 前缀 `/api/v1`、复用 DaisyWind 远端 PG 新建 db `cocowork`。服务在 `127.0.0.1:7999` 跑通。

## 后续使用方式
- 每次开启新的 AI 对话时，先读取这个文件。
- 每次完成有意义的开发后，更新这个文件一次。
- 可以直接用类似 `更新 context`、`把这次改动写入 context`、`压缩 context` 的指令触发维护。
