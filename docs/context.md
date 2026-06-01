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
- **前端知识库模块 CRUD 接通**：库级 list/get/create/update/delete 全对接后端 `/knowledge-bases`；列表页卡片网格 + 详情页（库信息 header + 文档/检索测试/设置 三 tab）；删除入口双处（卡片三点 + 设置页）。**检索测试 tab 已接真接口**（片6，见下）；**文档列表三点 Dropdown 接通**（下载占位 toast / 删除 AlertDialog 二次确认 + 本地 state 移除）；文档上传 sheet 仍 mock，等后端 4b-2/4b-3。
- **后端存储抽象层就位**：`app/core/storage/`（`Storage` ABC + R2/Local 双实现 + 按 `STORAGE_BACKEND` 装配的模块级单例 `storage`）；R2 支持预签名直传/下载、Local 走后端中转 + 路径穿越防护；同步 IO 全包 `asyncio.to_thread`、boto3 client 懒加载。
- **知识库文档上传 + CRUD 后端齐全（片4 完工）**：8 个端点全挂 `/knowledge-bases/{kb_id}/documents/*` 下。上传 3 个：`upload-init` 按 `supports_presigned` 返 `strategy=presign|passthrough` / `upload-passthrough`（仅 Local）/ `upload-complete`（仅 R2 + head 验对象在）；CRUD 4 个：list / detail / delete（联动清 storage）/ download-url（统一接口，R2 返 presigned GET 带 RFC 6266 filename / Local 返 raw 路径）；下载 1 个：`/raw`（仅 Local，StreamingResponse 吐字节）。Storage 扩 `stat_size` 复校真实大小，超限自动清干净。扩展名 md/txt + 大小上限 50MB。
- **知识库前端文档全流程接通**：`api/knowledge.ts` 7 函数（含裸 XHR 真进度的 `uploadDocumentToR2` + axios `onUploadProgress` 的 `uploadDocumentPassthrough`）；DocumentList 接 `Document` 真类型、`<a download>` 触发下载、AlertDialog 删除；UploadDocumentSheet 真上传状态机（Promise.allSettled 并发 + setQueue 函数式更新 + 单文件失败不影响其他）；R2 桶 CORS + Object R&W token 配妥。**上传 / 列表 / 下载 / 删除全链路 OK**。
- **知识库处理管线（片5 完工）全栈打通**：后端 Splitter 抽象层（`Splitter` ABC + `LangChainSplitter` 包 langchain `RecursiveCharacterTextSplitter`，v2 自研对照 swap 业务零改动）+ `process_document(doc_id)` 入口（解析→切段（双换行）→ 切块→批量 embed，状态机 status/stage 推进、try/except 兜底 failed、重入清旧 paragraphs FK CASCADE 自动连带清 embeddings）+ 触发端点 `POST /documents/{id}/process`（service 状态校验 uploaded/failed 可触发、`BackgroundTasks.add_task` 异步跑）；模型层 enum 改造（`KBStatus / DocStatus / DocStage / SourceType` StrEnum + `CharEnumField`，迁移 0007/0008 no-op SQL）；前端三点菜单加「向量化/重试向量化」入口 + 1.5s setTimeout 单次轮询自动续 + 乐观更新（点击立即 setDocs 标 processing，避开 BackgroundTasks 启动 race）。**上传 → 待向量化 → 触发 → 处理中 → 就绪 端到端 OK**。
- **知识库检索 + 命中测试（片6 完工）全栈打通**：后端检索 service（query 向量化 → 原生 SQL `embedding::vector(dim) <=> query` 余弦距离 → `DISTINCT ON (paragraph_id)` 按段去重取最近子块 → 外层阈值过滤 + 重排 + top_k；`{dim}` f-string 拼类型修饰符、向量/kb_id/阈值/top_k 走 `$` 参数防注入）+ 端点 `POST /knowledge-bases/{kb_id}/retrieval-test`（归属校验 + query/top_k/similarity_threshold）；schema `RetrievalTestIn`/`RetrievalHit`（父子块：返整段 content + 命中子块 chunk_text + score=1-距离）；前端 `runMockRetrieval` → `retrievalTest` 真接口、检索 mock 删净。**端到端 OK**。**命中测试首次暴露切块问题**：双换行段切分对 list-heavy md 失效（一整天行程挤成一巨段、命中返整段过长）→ 留 v2 heading 感知切块当对照案例。**RAG v1 六片整片收官。**
- **前端 admin 用户管理页（mock）**：`/admin/users` 表格（用户/邮箱/角色 badge/状态 switch/创建时间/删除）+ 搜索过滤 + 角色筛选 + AlertDialog 二次确认；自己的行禁用 switch 和删除；纯前端 mock，后端 user 管理接口齐了再换。
- **Agent 模块设计 spec 定稿**：`docs/design/agent-module-v1.md`（14 节产品+架构 spec）+ `agent-module-frontend-v1.md`（前端画法指南）。
- **Agent 模块前端切片 0 全栈打通（纯 mock）**：列表页三带式（模板池 + 我的 Agent 网格）+ 创建弹窗（选模板起名）+ 详情页（左 ConfigPanel 配置 40% / 右 Playground 沙盒试运行 60%，配置即时落 store）；`agent-mock-store`（zustand 列表/详情共用）。**砍掉「正式对话」**——详情页只做沙盒，正式对话归 workspace。后端 Agent 模型 + LangGraph 未起。
- **Workspace 模块前端完整骨架（纯 mock + local state）**：列表页卡片网格（成员头像堆叠 + 管家戴皇冠 + +N 折叠）+ 创建弹窗（带默认管家 + 初始对话）+ 详情页三栏（通讯录 240 / 主对话 flex-1 / 产出物 320，两侧均可独立收起）+ 招募弹窗两 tab（选模板 / 选 Agent，对齐 spec 三层分离）+ Conversation 切换条（顶部 popover 列出历史 + 「新对话」，切换走 `key` 重挂清消息）。主对话区核心 = **@mention 自动补全 popover**（光标前正则检测 `@<query>` → 候选成员浮层 → 点选替换光标位文本）+ mock 双轨路由（@某成员 → 那成员答，否则 → 管家答）+ assistant 气泡带头像（管家皇冠 / 成员色块）+ 品牌色名字。统一容器样式 `bg-background border shadow-sm overflow-hidden rounded-lg`（修圆角被子元素方角覆盖问题）。后端 Workspace 数据模型 + 注入引擎 + LangGraph 调度未起。
- **全局：路由→tab 自动同步机制**。路由 `staticData` + `useTabSync`（router onResolved 事件驱动），调用方只 `navigate`、tab 自动跟随；详情页 `useTabTitle` 覆盖动态名。工作台 + admin 两套 tab 都接入。

## 下一步
- **知识库 / RAG 模块 v1 整片完工（片1-6 收官）+ 收尾增强**：数据层 + KB CRUD + 存储抽象 + 文档上传/下载 + 处理管线 + 检索/命中测试全栈打通；**增强**：文档批量向量化/删除（部分成功语义）、命中测试检索耗时展示、文档列表段数展示、触发同步置 processing 修「刷新后轮询丢失」。
  - **方案见** `docs/design/knowledge-rag-v1.md`（spec + §13 切片清单全部勾掉）+ `knowledge-rag-decisions.md`（决策/权衡）。六片：VectorField + pgvector + 4 表迁移 0005 + AIModel.meta 0006 + KB CRUD + 存储抽象 R2/Local + Document 上传 CRUD 下载 8 端点 + Splitter 抽象层 + `process_document()` + 触发端点 + enum 化迁移 0007/0008 + 检索 service + 命中测试端点。详见最近迭代。
  - **v2 方向**：混合检索 / FTS / RRF / rerank / 多向量；切块优化（heading 感知——命中测试已暴露双换行段切分对 list-heavy md 失效，留作自研切块器 A/B 对照案例）；评估体系（Recall@k/MRR + LLM 自动造测试集）。
  - 既有决策：embedding 每库锁一个模型、rerank 先阿里、全文检索先 Postgres 原生 FTS（不够再上 ParadeDB pg_search，不上 ES）、切块默认（递归~512token+50overlap）+ 可配；混合检索/FTS/RRF/rerank/多向量 = v2；文档编辑用自封装 tiptap（后做）。
- **Agent 模块（设计已定稿，前端可独立推进）**：完整 spec 见 `docs/design/agent-module-v1.md`（14 节）+ 前端画法指南 `agent-module-frontend-v1.md`（三批实施建议）。范式 = 工作空间 + 单 agent 双入口；不调试不发布；模板/Agent/实例三层分离（模板=平台预置纯 LangGraph 行为骨架空壳，Agent=用户装备好的资产，实例=空间内成员含注入）；@直连 vs 不@走管家双轨调度；3 层长期记忆 L1/L2/L3 严格作用域。架构亮点：Hybrid Schema（核心列+jsonb 扩展）+ 三层分离（ContextBuilder/LangGraph/PostProcessor）+ 7 设计模式（Builder/CoR/Strategy/Mediator/Repository/Observer-EDA + Layered）+ Hexagonal。**前端切片 0 已完成**（列表/创建/详情配置/沙盒，纯 mock + local state，旧 agent 代码已替换；详见最近迭代）；后续切片 1+（模板 seed / Agent CRUD 接 API / 对话接 LLM）+ 后端 Agent 模型 + LangGraph 待知识库 RAG 收尾后启动。设计已砍 agent 详情页「正式对话」——正式对话归 workspace。
- **Workspace 模块（前端骨架完成，等后端起）**：列表 + 详情三栏 + 招募 + Conversation 切换 + @mention 双轨路由 mock 全画完（最近迭代）；后端待做：Workspace 模型 + CRUD（切片4）→ 实例注入引擎（切片5）→ supervisor LangGraph 调度（切片7+），跟 Agent 模块切片大纲走。
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

### 2026-06-01 — 知识库收尾增强：批量操作 + 检索耗时 + 段数展示 + 轮询修复

3 个 commit（片6 之后）：

- **批量操作（commit 3982d0a）**：后端 `DocumentService.trigger_progress_many`（返 `(triggered, skipped)`，部分成功语义）+ `delete_many`（返计数），各一次 `id__in` JOIN 查 + bulk 写避 N+1；端点 `POST .../batch-process`（逐个入队后台任务）+ `.../batch-delete`；前端 `DocumentList` 多选（行 checkbox + 全选三态 + 操作栏）+ 装 shadcn checkbox。
- **检索耗时 + 段数（commit 158d1e6 一部分）**：检索响应从 `list[RetrievalHit]` 包一层 `RetrievalTestOut`（hits + embed_ms/search_ms/total_ms），service `perf_counter` 夹两段计时（不落库仅展示，对标 ES `took`）；命中测试面板墨绿 Timer pill 展示耗时；`DocumentList` 行内加段数（`N 段 · M chunks`，未处理不显示）。
- **轮询丢失修复（commit 158d1e6 一部分）**：`trigger_progress`/`trigger_progress_many` 触发时**同步**置 `status=processing`（先标 in-flight、再入队），修复刷新后乐观态丢失 + DB 还没 processing → 轮询不续的问题。`process_document` 再设一次幂等无害。

### 2026-06-01 — 知识库片6 全栈：检索 service + 命中测试端点 + 前端切真接口（RAG v1 收官）

**后端检索 service（`retrieval_service.py`，含设计取舍故归用户写）**

- `RetrievalService.retrieval_test(user, kb_id, query, top_k, similarity_threshold)`：① `KnowledgeBase.filter(id, created_by=user).prefetch_related("embedding_model__provider")` 校验归属 + 取 embedding 模型 ② `ModelClient.create_embedding` 把 query 转**一条**向量 → pgvector 文本字面量 `[..]` ③ 原生 SQL 走 `connections.get("default").execute_query_dict`。
- **检索 SQL（两层）**：内层 `DISTINCT ON (paragraph_id)` + `ORDER BY paragraph_id, distance` 按段去重、每段取最近子块（DISTINCT ON 强制以 paragraph_id 打头、顺序被绑死）；外层 `WHERE (1-distance) >= threshold` + `ORDER BY distance` 重排 + `LIMIT top_k`。
- **参数化要点**：`{dim}`（= `kb.embedding_dim`）是**类型修饰符**语法上不能参数化 → f-string 拼入（DB int 安全）；query 向量 / kb_id / 阈值 / top_k 全 `$1-$4` 防注入。cast 写法须与将来按库建的 HNSW 部分索引表达式一致才命中。`source_type='content'` 写死（v1 唯一，给多向量留口子）。score = 1 - 余弦距离。

**schema（用户写）+ 端点（Claude 写）**

- `retrieval_schema.py`：`RetrievalTestIn`（query + top_k 1-50 + `similarity_threshold` 默认 0=不过滤，方案 B 加的第三旋钮）+ `RetrievalHit`（父子块：返整段 `content` + 命中子块 `chunk_text` + `score`）。
- 端点 `POST /knowledge-bases/{kb_id}/retrieval-test` → `ResponseModel[list[RetrievalHit]]`，加在 `knowledge_base.py`（单端点不拆文件）。

**前端切 mock → 真接口（Claude 写）**

- `types/knowledge.ts` 加 `RetrievalHit`；`api/knowledge.ts` 加 `retrievalTest(kbId, query, topK)`；`RetrievalTest.tsx` `runMockRetrieval` → `retrievalTest`、key 换 `paragraph_id`；`mock.ts` 删 `RetrievalChunk`/`sampleChunks`/`runMockRetrieval`（只留状态徽标）。组件渲染没动（字段名后端对齐 mock）。`tsc --noEmit` 0 报错。

**端到端验收 + 发现**

- 起后端 + 已向量化 KB → 命中测试输入 → 真命中段 + 分数、DISTINCT ON 去重生效。✅
- **命中测试首次暴露切块问题**：旅游计划 md 一整天行程（多景点）无空行 → `_split_paragraphs` 双换行切分把它挤成**一个巨型段** → 命中返整段过长（父子块按设计返整段，问题在段切太粗）。属 v1 已知局限，留 v2 heading 感知切块 + 自研切块器 A/B 对照（decisions §13.4）。**命中测试作为「索引体检」的价值即时兑现。**

**SQL 写法选型（讨论沉淀）**

- raw SQL 组织：内联参数化 vs 外置 `.sql` 文件 vs query-builder 编译注入（MaxKB）三档，**按规模匹配**——单条短查询内联最干净；规模涨先升「命名常量」再升「.sql 文件」；动态结构才上 query builder（SQLAlchemy Core/PyPika），不学 MaxKB 土法注入。我们 v2 三模式是「3 条固定 SQL + mode 选 + blend 走 Python RRF」，不需注入机器。

### 2026-05-29 — 知识库片5 全栈：处理管线 + 触发端点 + enum 改造 + 前端入口轮询乐观更新

**后端 5.1 Splitter 抽象层**

- `app/services/knowledge/splitter/`：`Splitter` ABC（`split(text, config) -> list[str]`）+ `LangChainSplitter` 包 langchain `RecursiveCharacterTextSplitter`（v1 baseline）+ 模块级单例 `splitter`。v2 自研对照见 decisions §13，swap 装配一行、业务零改动。
- 装 `langchain-text-splitters` 子包（不引全套 langchain）；chunk_size/overlap 用库级 `ChunkConfig`，默认 separators 走 `["\n\n", "\n", " ", ""]`。

**后端 5.2 `process_document` 管线主函数**

- 入口 `Document.get_or_none(id=doc_id).prefetch_related("knowledge_base__embedding_model__provider")`——**踩坑**：原本三层 `select_related` 嵌套触发 Tortoise 1.x `_fk_setter` 把 UUID 当 model 实例（`AttributeError: 'UUID' object has no attribute 'id'`），换 prefetch_related 走分多条 SQL 独立 _init_from_db 即稳。代价多几条 SQL，pipeline 场景可忽略。
- 状态机：入口 `status=processing/stage=parsing` → 切段 `stage=splitting`（按双换行切段朴素版，v2 加 md heading）→ 切块 + 批量 embed `stage=embedding` → 收尾 `status=completed/stage=NONE`；任一步异常 → `status=failed` + `error_message`，stage 留在出错那步。
- **重入策略**：开头 `Paragraph.filter(document_id=doc.id).delete()` 清旧（FK CASCADE 自动连带清 embeddings），允许 failed 重试 / 完成后重切。
- **不开事务**：每步分阶段 save 让前端轮询能看到 stage 推进；BackgroundTasks 拿不到异常，try/except 整体包 + 失败落库 + log。
- **分批 100 调 embedding**：汇总所有段子块 `[(paragraph_id, position, text), ...]` → 切片 batch 100 → 1 次 `ModelClient.create_embedding` + 1 次 `Embedding.bulk_create`；避撞 OpenAI/阿里单请求 input 上限。
- **UUID7 Python 侧生成**：bulk_create 后 in-place 对象 id 已有、可直接复用挂 FK。

**后端 5.3 触发端点**

- `POST /knowledge-bases/{kb_id}/documents/{doc_id}/process`：`DocumentService.trigger_process` 状态校验（`stage=uploaded` 首次 / `status=failed` 重试可触发，processing/completed/pending 字节未传一律拒绝）+ `BackgroundTasks.add_task(process_document, doc.id)` 异步入队 + 立即返回。

**模型层 enum 改造（顺手收口）**

- `app/models/knowledge.py` 顶部加 4 个 StrEnum：`KBStatus` / `DocStatus` / `DocStage`（含 `NONE=""` 占位）/ `SourceType`（content/question/title v2 多向量留口子）。
- 4 个字段（KB.status / Document.status,stage / Embedding.source_type）`CharField` → `CharEnumField`，max_length 不变 DB 列定义等价；service 6 处字符串赋值换 enum 引用。
- 迁移 0007（knowledge_enum_status）+ 0008（embedding_enum_source_type），SQL 几乎 no-op（仅 schema 元数据更新、default 字面量相同）；StrEnum 继承 str 向后兼容、老字符串赋值仍可写入。
- 收益：IDE 补全、防拼错；DB 读取自动转 enum 实例。
- 决策：MaxKB 那种位运算多任务状态字符串 v1 不学（参考 decisions §11）；将来真要多任务（rerank / 生成假设问题）走 JSONB / 子表，不走位运算。

**前端 trigger + 轮询 + 乐观更新**

- `api/knowledge.ts` 加 `triggerProcessDocument`；`DocumentList` 三点菜单加「向量化 / 重试向量化」入口（仅 `display=uploaded/failed` 显示）。
- `KnowledgeDetailPage` 加轮询 useEffect：`docs.some(d => d.status === 'processing')` 时 `setTimeout(refetchDocs, 1500)`，单次触发 + cleanup 自动续；全部脱离 processing 自动停。
- **乐观更新解 race**：原本 trigger 后立即 refetch 太快、BackgroundTasks 还没设 status=processing → 轮询条件不成立、永远不轮。改 `onProcessed(docId)` 父级 `setDocs` 立即本地标 `processing/parsing`，UI 即时反馈 + 轮询条件立即成立、后端真实状态轮询回填。
- 端到端：上传 → 待向量化 → 点向量化 → 处理中 pulse → 就绪。

**收口**

- §13 片5 勾掉；只剩**片6 检索 + 命中测试**（前端 RetrievalTest 组件已 mock 就位、后端接入只换函数实现）。

### 2026-05-28 — 知识库片4 全栈：后端 4b-2/4b-3 + 前端文档真接通 + R2 download filename RFC 6266

**后端 4b-2 / 4b-3（8 个端点）**

- **4b-2 上传（3 个）**：`upload-init`（建 pending + 按 `supports_presigned` 返 `strategy=presign|passthrough`）/ `upload-passthrough`（仅 Local）/ `upload-complete`（仅 R2 + head 验对象在）。调错路径直接 `ValidationException` 拒绝。
- **4b-3 CRUD + 下载（5 个）**：`GET /documents` / `GET/DELETE /documents/{id}` / `GET /documents/{id}/download-url`（按 backend 返 R2 presigned GET / Local raw 路径）/ `GET /documents/{id}/raw`（仅 Local，StreamingResponse 吐字节）。
- **Storage 扩 `stat_size`**：R2 用 head_object 取 ContentLength、Local 用 path.stat()；给上传完成后复校真实大小用（前端 init 时声明的 size 可能撒谎、必须后端跟 storage 确认）。
- **service `mark_uploaded`**：复校 → 超限清干净（storage.delete + ORM delete）+ 抛错；正常更 size + 置 `stage="uploaded"`。不加字段、复用 stage 表达。
- **MIME 后端定**（md→text/markdown / txt→text/plain）；R2 presign 钉 Content-Type、前端 PUT 必须带相同 header。
- **流程对称**：R2 3 步（行业标准 AWS S3/OSS 同款）+ Local 2 步；砍 Local 到 1 步价值低 + 前端分支反而复杂，弃。

**前端 D-1 / D-2 / D-3（文档全流程真接通）**

- **D-1 types + api**：`Document` / `DocumentStatus(pending|processing|completed|failed)` / `DocumentStage('' | 'uploaded' | parsing/splitting/embedding)` / `UploadStrategy('presign'|'passthrough')` / `UploadInitOut`；`api/knowledge.ts` 加 7 函数：listDocuments / deleteDocument / getDocumentDownloadUrl / initDocumentUpload / confirmDocumentUpload / **uploadDocumentPassthrough**（axios 自带 `onUploadProgress`）/ **uploadDocumentToR2**（**裸 XHR** 真进度——避开 axios 拦截器对 R2 空响应误解包，行业 fetch 不支持 upload progress 标准缺口）。
- **D-2 DocumentList + KnowledgeDetailPage 接真接口**：mock 清掉（删 mockDocuments/KnowledgeDoc/DocType/DocStatus）；加 `getDocDisplayStatus` helper 把后端 (status, stage) 映射成单一展示态 `uploading|uploaded|processing|completed|failed`；下载用 `<a download>` 程序触发（GitHub/Drive 同款）；删除走真接口 + AlertDialog；dayjs `fromNow()` 相对时间。
- **D-3 UploadDocumentSheet 真上传状态机**（值得动脑的部分）：抽 `uploadOne(item, onProgress)` 封装 init→上传→(R2 才有 complete) 三步；`startUpload` 用 **Promise.allSettled** 并发跑、`setQueue((prev) => …)` 函数式更新避免 React 异步丢进度；单文件失败不影响其他、记 error message；大小上限 50MB 对齐后端。
- **R2 直传两关**：① CORS（R2 桶 Settings 配 AllowedOrigins=localhost:7777 + Methods=GET/PUT + AllowedHeaders=*）② API token 必须 **Object Read & Write**（不是只读）。PUT 成功后 response body 是空的（S3 协议设计），DevTools 显示 "Failed to load response data" 正常。

**R2 download filename + RFC 6266**

- 痛点：R2 是跨域，`<a download>` 属性失效；下载文件名靠 `Content-Disposition: attachment` header 决定；R2 默认不带 → 浏览器可能预览不下载、文件名是 storage_key UUID 而非原始名。
- 改造：`Storage.generate_download_url` 加可选 `filename` 参数；R2 实现把 `ResponseContentDisposition=attachment; filename="..."; filename*=UTF-8''<encoded>` 塞进 presigned URL；`/raw` 端点 header 同步；下载端点调时多传 `filename=doc.name`。
- 防护：sanitize 去引号/换行防 header 注入；RFC 6266 `filename*=UTF-8''` 中文不乱码。GitHub/Drive/Dropbox 同款做法。
- **片4 整片收口**：8 后端端点 + 前端真接通 + R2 直传/下载全通；等进片5 处理管线（手动触发向量化）。

### 2026-05-28 — Workspace 模块前端完整画完（列表/三栏详情/@mention/Conversation）+ KB 检索测试 mock + 文档三点 + 卡片三点统一

- **Workspace 模块前端骨架（纯 mock + local state，对齐 spec §5/§6）**：types/workspace.ts（WorkspaceMember + Conversation + Workspace，画图占位 schema、成员/对话内嵌）+ mock（3 空间，成员复用 agent mock 人设）+ `workspace-mock-store`（zustand，含 `addConversation`）。
- **列表页 `/workspaces`**：Header + 卡片网格 + 创建弹窗（默认带管家 + 初始 conversation）；`WorkspaceCard` 成员头像堆叠（管家戴皇冠 + 最多 4 + +N 折叠）+ 三点删除（AlertDialog + 关 tab）。
- **详情页 `/workspaces/$workspaceId` 三栏**：通讯录 240（管家固定第一 + 来源标签 + 招募按钮 + X 收起）/ 主对话 flex-1 / 产出物 320（占位空态 + X 收起）。**两侧均可独立收起**，关闭后顶部出 `PanelLeft / PanelRight` toggle 按钮恢复。统一容器 `bg-background border shadow-sm overflow-hidden rounded-lg`——`overflow-hidden` 是关键，否则子元素方角覆盖外层圆角。
- **主对话区核心（spec §5.4 + §6 双轨）**：复用 Playground 气泡 + 输入区模式 + 加两特性 = ① **@mention 自动补全 popover**（textarea ref + 光标 selectionStart 检测最后 `@<query>` 正则 + 候选成员浮层 + 点选 `before.replace(/@([^\s@]*)$/, '@${name} ')` + setSelectionRange 复位光标） ② **mock 路由**（消息开头 `@某成员` → 那成员答；否则 → 管家答）；assistant 气泡带头像（管家皇冠 / 成员色块）+ 品牌色名字标注；消息纯内存、刷新即清；切 conversation 走 `<WorkspaceChat key={convId} />` 重挂清空。
- **招募弹窗（spec §5.2）**：两 tab「从模板 / 从我的 Agent」共用头像 + 名 + 描述卡片形态；招进来都是该空间实例（v0 简化复制基础字段，跟源脱钩对齐 spec §3.4）。
- **Conversation 切换条**：主对话区顶部独立 row（跟 WorkspaceChat 共享外层 border 容器，WorkspaceChat 顶层改 Fragment 让父统一包）；当前标题 + ChevronDown popover 列出按 updated_at 倒序的历史 + 「+ 新对话」按钮 push 进 store 并自动切换。
- **KB 检索测试 tab 接 mock**：从 TabPlaceholder 占位换成 `RetrievalTest`（query Textarea + topK Select(3/5/10/20) + Cmd/Ctrl+Enter 触发 + 四态结果区）；`runMockRetrieval` 500ms 延迟 + 6 段贴近真实业务的 chunk 文本（白皮书 / API 指南 / 用户手册 / FAQ / 更新日志）+ 递减相似度（0.92 起步、每条 -0.07、最低 0.3）。后端片6 接入只换函数实现，组件不动。
- **KB DocumentList 三点 Dropdown**：抽 `DocumentRow` 子组件管 confirm state；「下载」（占位 toast）+「删除」（AlertDialog 二次确认）；KnowledgeDetailPage 传 `onDelete` 让 mock 真生效。
- **卡片网格三点位置统一右上角**：AgentCard / ProviderCard / KnowledgeCard / AIModelCard / WorkspaceCard 五张卡片三点都到顶部右上角。KnowledgeCard 顶部状态点 + label「就绪」**挪到底部 embedding badge 行最左**；AIModelCard「✓启用」图标**挪到左侧类型 badge 旁**——避免「状态信息 + 操作菜单」两类元素挤同一角；删 4 处 `translate-y-3` 旧底部对齐 hack，统一用 `-mt-1` 微调。

### 2026-05-28 — Agent 模块前端切片 0（列表三带式 + 详情左配右沙盒）+ 路由→tab 自动同步 + 砍正式对话

- **切片 0 完成（批次 1+2+3，纯 mock + local state）**：`types/agent.ts` 重写（`Template`/`Agent`/`AgentConfig`/`Message`，删旧 status/agent_type）；`mock.ts`（8 模板 + 5 Agent 含裸 Agent + ChatModel/Knowledge/Tool mock）；`AgentsPage` 三带式（Header + 模板池横向带 + 我的 Agent 网格）；`AgentCard`/`TemplateCard`/`CreateAgentDialog`；`AgentDetailPage`（左 `ConfigPanel` 40% + 右 `Playground` 沙盒 60%）；`agent-mock-store.ts`（zustand，列表/详情共用，刷新还原）。
- **全局机制：路由→tab 自动同步**。各叶子路由加 `staticData: {tabTitle, tabIcon}`；`stores/use-tab-sync.ts` 的 `useTabSync` 用 `router.subscribe('onResolved')` 在导航完成后同步 tab（避开 selector 多取值错位/title 串台），调用方只写 `navigate` 不再手动 `openTab`；详情页 `useTabTitle(path, name)` 覆盖动态名（path 由 `useParams` 派生 + 订阅「该 path tab 是否已存在」：解决 ① 同路由 params 切换复用组件时 title 串台 ② open/setTitle 时序竞争导致 tab 卡在 fallback 名）。删了 7 处 openTab 双调用；AppShell/AdminShell 各接一次。
- **产品简化：砍掉 agent 详情页「正式对话」**，只留沙盒试运行（消息纯内存、刷新即清）；正式对话归 workspace 模块（避免「同一对话能力两个入口」心智冲突）。`docs/design/agent-module-frontend-v1.md` 同步更新（§6/§10/§11 + 布局图改 40/60 单一沙盒）。
- 配套：装 shadcn `popover`/`command`/`breadcrumb`；nav 加「工作空间」(Layers icon) + `/workspaces` 占位页；`ConfigPanel` 用方案 A（无外框 + Separator 分段 + header 区放大头像/名字）；抽 `hooks/use-horizontal-wheel-scroll.ts`（模板池 + TabBar 横向滚轮共用）；`PagePlaceholder` 加可选 `description`。
- **App Shell 高度链锁定**：`SidebarProvider` `min-h-svh`→`h-svh` + 内容 wrapper 补 `min-h-0`，详情页全程 `flex-1`+`min-h-0` 配对，Playground 内部消息区自滚、输入区贴底，整页不再溢出。

### 2026-05-26 — Agent 模块设计 spec 定稿 + admin 用户管理页（mock）

- **核心产出**：`docs/design/agent-module-v1.md`（14 节产品+架构 spec）+ `agent-module-frontend-v1.md`（纯前端画法指南，三批实施 + 类型/mock/布局/交互全描述、不涉及代码）。设计未实施，今天只动手了 admin 用户管理页占位。
- **范式定型**：工作空间 + 单 agent 双入口（Agents `/agents` 单 agent / Workspace `/workspaces` 多 agent 协作）；**砍掉调试-发布二元状态**——配置即时生效；模板/Agent/实例**三层分离**：模板=平台预置纯 LangGraph 行为骨架空壳（无 prompt 无资源、用户不可建不可改），Agent=用户基于模板装备的资产（挂 prompt/模型/资源），实例=空间内成员（由模板或 Agent 复制 + 空间注入）。Sidebar 加 Workspace 项放 Agents 之上。
- **关键决策**：`@某 agent 直连` vs `不@ 走管家` 双轨调度（@ 直连贴 Slack 直觉）；subagent 用完即销毁；资源三层（自带/共享/实例覆盖）取并集去重；3 层长期记忆 `L1 用户画像(user)` / `L2 空间世界观(workspace)` / `L3 实例工作记忆(workspace,instance)`——agent 自身无跨空间状态，仅 L1 跨空间。Agent 列表页**三带式**（Header + 模板池横向卡片条 + 我的 Agent 网格），创建 Agent = 选模板 + 起名。
- **架构亮点（§10-11，简历加分）**：① **Hybrid Schema**（核心字段用列+扩展字段 jsonb，避免大 JSON / EAV / 全固定列三种反模式）；② **三层分离架构**（Build-Execute-Postprocess）：ContextBuilder→LangGraph→PostProcessor，LangGraph 只负责业务编排，**反对把上下文注入塞进 LangGraph 节点**（明确反模式）；③ **7 个设计模式**：Layered / Builder（ContextBuilder fluent API）/ Chain of Responsibility（注入责任链——加新注入类型只加 Injector 不动其他）/ Strategy（行为模板 + 调度算法）/ Mediator（supervisor 本质）/ Repository（数据访问抽象）/ Observer-EDA（沉淀解耦）；④ **3 个高阶概念**：Hexagonal Ports & Adapters / EDA / CQRS（v2+）。各模式都附简历叙述版。
- **业界对照（spec 附录 B）**：MaxKB 单 agent 固定字段 / Dify 工作流画布 / LangChain Runnable / CrewAI dataclass / OpenAI Assistant 固定 schema / Claude Code 后台 Task tool；CoCoWork 定位 = **同会话多 agent 接力 + @ 直选 + Hybrid Schema + 注入引擎**。Context Engineering 是产品 narrative，Configuration Composition with Hybrid Schema 是技术叫法。
- **v1 切片大纲（11 片）**：切片 0 前端基建（nav+workspace 占位+agent 三带式列表+左配右聊详情骨架，纯 mock）→ 1 模板 seed → 2 Agent CRUD → 3 单 agent 对话 → 4 Workspace CRUD → 5 招募注入 → 6 工作空间详情页 → 7 supervisor+@路由 → 8 长任务+SSE → 9 subagent → 10 产出物。**前端切片 0 可独立于后端推进**。
- **admin 用户管理页（mock）**：`pages/admin/UsersPage.tsx` + `users-mock.ts` + 路由接上；表格（头像+username/邮箱/角色 badge/状态 switch/创建时间/删除）+ 搜索 + 角色筛选 Select + 自己行禁用 switch/删除（tooltip 提示）+ AlertDialog 二次确认；纯前端，后端 user 管理接口齐了再接。
- **设计纠结过程**：曾陷入「多 agent 看着像 MaxKB 复制品」「Claude Code 也有 subagent，我换皮？」等焦虑——结论：差异化不在产品形态而在 narrative + 工程立场（Hybrid Schema + 注入引擎 + 三层分离），且 CoCoWork 服务"自用+简历+Star+艺术品"四目标交集，P3 完整版是最优解。设计阶段最大教训：完美主义瘫痪要靠"写一段最小代码跑出来用感觉替代想象"破局。
- **未做**：旧 `pages/agents/*` 仍是 status/agent_type 等过时字段；类型 / mock / 卡片 / 详情都未改造。计划随切片 0 实施一并替换（不预清理避免幽灵代码）。

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

## 历史摘要
- **2026-05-25 — 知识库/RAG 后端：片3 CRUD + Model 模块顺手补 dim 探测**：`/api/v1/knowledge-bases` 5 端点鉴权 + 用户可见；service 直接返组装好的 `KnowledgeBaseOut`（跨实体计算字段 model_validate 装不下）；Model 模块顺手改：validator.validate 返 dict 携 embedding_dim、AIModelService.create 写入 AIModel.meta（建模型即落库 dim，零额外上游调用），ModelOut 加 meta 对外暴露；建库 dim 解析先 model.meta 再 `_probe_embedding_dim` 兜底；计数 annotate-only 查 + 模型名单独 values_list 批量查（避 select_related + annotate 同用的 GROUP BY 报错）；决策：不许换 embedding 模型（换 = reindexing 全库重建）、update 只允改 name/description/chunk_config、删库 FK CASCADE 清下游。
- **2026-05-25 — 知识库前端：设置页接通 + 卡片删除入口**：`KnowledgeSettings` 保存/删除接真 API（updateKB silent + deleteKB + 关详情 tab + 跳回列表）；`KnowledgeCard` 仿 ProviderCard 加三点 dropdown + AlertDialog；删除入口卡片三点 + 设置页两处对齐；ProviderCard 补关 tab；决策：设置页只允改 name/description，向量化配置锁死只读。
- **2026-05-24 — 知识库/RAG 设计定稿 + 数据层（片1+2）+ AIModel.meta**：spec `knowledge-rag-v1.md` + decisions 定稿；4 表 single-file（KB/Document/Paragraph/Embedding）+ 父子块（embed 子块、命中返整段、子块不落表、文本存 `embedding.text`）+ Embedding 独立表（一对多 + source_type + 多向量留口子）；pgvector 0.8.1 已装，自定义 `VectorField`（不锁维度、原生 SQL 相似度查询、按段 DISTINCT ON 去重）+ 部分索引 + 表达式 cast 与查询一致才命中；存储抽象延后到片4；v1 手动向量化（FastAPI BackgroundTasks，将来换 ARQ 不返工）；迁移 0005 已 apply（含 RunSQL CREATE EXTENSION vector）；AIModel 加 `meta` JSONField(null=True) 存固有事实（dim/context_window），懒填充 embedding_dim。
- **2026-05-24 — 知识库列表页 + 详情页前端（静态 mock）+ 模块 IA 决策**：`/knowledge` 三带布局（Header/统计带/卡片网格 + 虚线新建卡），左侧 `KnowledgeFolderTree` 预留壳（return null，两栏 flex 已就位）；详情页 `/knowledge/$kbId` = 面包屑 + 库信息 header + shadcn tabs（文档/检索测试/设置），文档用列表行、库列表用卡片网格（两层不同形态）。决策：详情页不做独立 sidebar 改用 tab。数据形状 `KnowledgeBase`/`KnowledgeDoc` 预埋；后续接 API。
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
