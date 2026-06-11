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
- **Agent 模块前后端整片打通（CRUD 接真接口）**：列表 / 创建 / 详情 / 保存 / 删除 5 端点全栈联通。列表页三带式（模板池 2 张：真 loop `general` + graph 占位 disabled / 我的 Agent 网格 / ldrs l-ring loader）+ 创建弹窗（`template + config` payload）+ 详情页（左 ConfigPanel 40% / 右 Playground 沙盒 60%）。**ConfigPanel 显式保存模式**：本地 form state + Sticky 顶栏「橙点·有未保存改动」+ 整体 PUT；`agentToForm` 摊平 / `save()` 时打包回 config jsonb；mock-store 退役。配置里 chat 模型 + 知识库选择器接真 `listAllModels({modelType:'chat',enabledOnly:true})` + `listKnowledgeBases()`；AgentCard meta 行真显模型名（父级一次拉 model map 避 N+1）。工具仍 mock（后端 tool 模块未起）；Playground 沙盒回复仍是 500ms 假回复待接 LLM。**砍掉「正式对话」**——详情页只做沙盒，正式对话归 workspace。
- **全局允许同名资源**：KB / Provider 删 `unique_together = (("created_by", "name"),)` 约束 + service 清理 try/IntegrityError + 迁移 0010；AIModel / Agent 本就没约束。对齐 ChatGPT custom GPT / Claude Project / Notion 行业惯例——列表 UI 靠头像 / 描述 / 时间区分，不用 name 唯一兜底。
- **Agent Playground 端到端 + 通用对话层整片完工**：后端 `runtime/`（events / adapter / runner，build_chat_model + prepare_stream + run_chat_stream）+ route `POST /agents/{id}/playground/stream`（StreamingResponse + 内联 ORM 归属校验）+ 路由挂载；前端 `types/chat.ts`（通用契约三层结构 + API snake_case 透传 / 内部 camelCase）+ `api/chat-stream.ts`（parseSSEStream + streamChat endpoint 形参注入 + AbortSignal 透传 + ChatStreamHttpError）+ `stores/chat-store.ts`（**Zustand 工厂 createStore + immer + 11 case dispatch + AbortController 内部维护 + messagesToHistory 摊平**）+ `components/chat/`（MarkdownRender + 三块组件 + MessageList 智能滚动 + MessageInput 停止按钮 + ChatProvider Context vanilla store + useStore）+ Playground 重写（useMemo + endpoint deps + unmount cleanup reset）。沙盒不入库前端持 history 摊平送；stop() 全链路真停（fetch abort → asyncio cancel → 上游 LLM 真停、不再吐 token）。**runtime / chat 命名都刻意避场景，workspace 真对话片直接 mount `createChatStore({ endpoint })` 全复用、零工作量**。底部 loader 走 ldrs `l-bouncy` + drop-shadow 暖橙发光做冷暖混色光晕。
- **Workspace 模块前端完整骨架（纯 mock + local state）**：列表页卡片网格（成员头像堆叠 + 管家戴皇冠 + +N 折叠）+ 创建弹窗（带默认管家 + 初始对话）+ 详情页三栏（通讯录 240 / 主对话 flex-1 / 产出物 320，两侧均可独立收起）+ 招募弹窗两 tab（选模板 / 选 Agent，对齐 spec 三层分离）+ Conversation 切换条（顶部 popover 列出历史 + 「新对话」，切换走 `key` 重挂清消息）。主对话区核心 = **@mention 自动补全 popover**（光标前正则检测 `@<query>` → 候选成员浮层 → 点选替换光标位文本）+ mock 双轨路由（@某成员 → 那成员答，否则 → 管家答）+ assistant 气泡带头像（管家皇冠 / 成员色块）+ 品牌色名字。统一容器样式 `bg-background border shadow-sm overflow-hidden rounded-lg`（修圆角被子元素方角覆盖问题）。后端 Workspace 数据模型 + 注入引擎 + LangGraph 调度未起。
- **全局：路由→tab 自动同步机制**。路由 `staticData` + `useTabSync`（router onResolved 事件驱动），调用方只 `navigate`、tab 自动跟随；详情页 `useTabTitle` 覆盖动态名。工作台 + admin 两套 tab 都接入。
- **Agent 模块后端整片打通**：`agents` 表（Hybrid Schema：核心列 + `config` jsonb，迁移 0009）+ CRUD（schema/service/route，5 端点 `/api/v1/agents`，归属隔离 + `get_template` 校验 + template 创建后锁死）+ **模板层 `app/agents/templates/`**（三层基类 `AgentTemplate/LoopTemplate/GraphTemplate` + 装饰器注册表 + `builtin/general`）。**结构 1+N**：1 个可配置 loop 引擎（能力靠 `config.capabilities` + 注册表 + 装配器组合，占位待接 LLM）+ N 个 graph 模板（首批 0）。前端 mock 待接真接口。
- **工具模块第一刀（builtin 一脉）整片打通**：后端 `app/tools/`（CoCoTool 基类——模板方法模式统一兜 cap / timeout / 异常 + 项目元信息 display_name/source_type/dangerous + registry 启动期 name 正则 fail-fast + builtin/calculator 用 AST 白名单求值零依赖防注入防 CPU 炸弹）+ `AgentConfig.tools: list[UUID]` → **`builtin_tools: list[str]`**（按来源分字段，未来 mcp/custom 各加字段不破坏 jsonb 存量数据，对齐 OpenAI Assistants 分字段形态）+ `runner.prepare_stream` 经 **`_assemble_tools` 单装配点** 喂 `template.build(tools=...)`（新来源在此扩、调用方一行不动）+ `GET /api/v1/tools` 工具列表接口（`ToolOut`：name/display_name/description/source_type/dangerous，所有来源同结构）；前端 `types/tool.ts` + `api/tool.ts` + ConfigPanel 工具选择器接真接口（mock 全删，存 name 字符串而非 UUID）；ToolUseBlock 视觉收尾：去 Loader2 转圈、统一静态 Wrench、状态色 success=brand/error=destructive/running=muted。**LLM 真能调 calculator 给出精确结果**。**RAG 维度确认**：Agentic RAG = LangChain/LangGraph 官方推荐架构，KB 未来走 tool 同入口（装配器 wrap 成 bound retriever tools）、不塞 system prompt。**上下文管理路线**：L1（每工具 output cap，CoCoTool 已收口）+ L4（Anthropic SDK `clear_tool_results` 一行配置）；L5 summary 索引外置 = Devin 级重武器、独立开发者不碰。
- **KB-as-tool 后端整片打通**：检索层 `app/services/knowledge/retrieval/` 子包重构成策略模式（base/vector/service + `RetrievalMode` StrEnum + `RetrievalParams` Pydantic + `RetrievalResult` dataclass + dispatch 入口）；老 `retrieval_service.py` 退场、`retrieval-test` 端点切到 `svc.retrieve(mode='vector', ...)` 老前端零改动同结果同字段。`KnowledgeRetrievalTool`（`app/tools/knowledge_retrieval.py`）per-KB bound 实例 + 不进 registry + `source_type="knowledge"` 字面量；只暴露 `query` 给 LLM（业界 LangChain `create_retriever_tool` 同款）+ `default_top_k=3` 装配阶段绑定。`_assemble_tools(cfg, user)` 单装配点扩 knowledge 来源（一次性 prefetch + filter `created_by` 归属校验，残留 id 自动跳过容错）；`prepare_stream(agent, request, user)` + playground route 联动加 user 形参。tool name = `knowledge_<kb.id.hex[:8]>`，description 拼 KB name + description 让 LLM 选库（Agentic RAG 业界范式）。**Playground 实测 LLM 主动调 KB tool 返 markdown 段落 + 相关度**。
- **Workspace 后端 d-1 前半段全栈打通**：4 表 model + migration 0011 + 三 entity CRUD（Workspace / Conversation / Message 共 11 端点）。**关键架构**：supervisor 自带不招募（存 `workspace.supervisor` jsonb 复用 AgentConfig schema，不进 agents 表）+ `unique(workspace, agent)` 阻重复招募 + Message 三层身份字段（`role` user/assistant 业界规范 + `sender_kind` user/supervisor/member 业务区分 + `sender_member_id` FK `SET NULL` 踢人保历史）+ `content` jsonb blocks 对齐前端 chat.ts + `mentioned_member_ids` 冗余 jsonb 给路由用 + `status` 三态 done/error/stopped + `thread_id = conversation.id.hex` 约定映射 LangGraph checkpointer（业务库 vs checkpointer 状态三分铁律不进 schema）。Conversation/Message 走 nested URL，归属校验靠 ORM JOIN 一次过。Message 只开 GET 列历史（写消息走未来 stream 端点，编辑/删 v1 不做）。**Runtime 解耦**：抽 `AgentSpec` frozen dataclass 作为 runner 输入契约，只装 `template + config`，`prepare_stream(agent: Agent, ...)` → `prepare_stream(spec: AgentSpec, ...)`；两 factory `from_agent` / `from_jsonb` 让 workspace.supervisor / 招进 workspace 的 member / 临时 NPC 全部零改动复用 runner，校验前置 factory 阶段、runner 不再二次防御。Playground 调用方改用 `AgentSpec.from_agent(agent)`。
- **Workspace d-1 对话整片全栈打通（stream + 落库 + 前端接真 + 配置面板）**：后端 runtime 事件总线化——adapter 改吐 `(EventType, payload)` 二元组（SSE 序列化收口 runner）+ runner `sink` 旁路钩子（Unix tee：一份前端一份落库，`_feed_sink` 兜异常不断主流）+ `MessageCollector` 桶（runtime 通用、只攒不判，status 由调用方控制流位置判定）；stream 端点 `POST .../conversations/{cid}/stream`（拉 DB 历史只回放 text「存而不喂」→ 先落 user → `AgentSpec.from_jsonb(supervisor)` 装配 → 流完 finally `asyncio.shield` 落 assistant 三态 + touch updated_at）；`ConversationStreamIn` 无 history 字段（谁持有历史谁拼：沙盒前端持、workspace DB 持）；流式 id == DB id（`MessageAppend.id` default_factory + 透传）；`from_jsonb` 砍「dict 里翻 template」假能力（template 改显式形参，脏数据 fail fast）。前端 workspace mock 全退役接真：types/api 对齐 11 端点 + 列表/详情/对话切换接真（无对话自动建）+ `WorkspaceChat` mount 通用 chat 层（`sendHistory:false` + `hydrate` + `chat-history.ts` 翻译器：stopped→completed、tool 无结局→calling 灰展示）+ 右栏「空间配置 ⇄ 产出物」FlipPanel 3D 翻转（默认配置面：管家 chat 模型 + system_prompt）+ `supervisorReady` 前置校验（未配模型输入框禁发指路）。@mention/mock 双轨退役待 d-3。

## 下一步
- **知识库 / RAG 模块 v1 整片完工（片1-6 收官）+ 收尾增强**：数据层 + KB CRUD + 存储抽象 + 文档上传/下载 + 处理管线 + 检索/命中测试全栈打通；**增强**：文档批量向量化/删除（部分成功语义）、命中测试检索耗时展示、文档列表段数展示、触发同步置 processing 修「刷新后轮询丢失」。
  - **方案见** `docs/design/knowledge-rag-v1.md`（spec + §13 切片清单全部勾掉）+ `knowledge-rag-decisions.md`（决策/权衡）。六片：VectorField + pgvector + 4 表迁移 0005 + AIModel.meta 0006 + KB CRUD + 存储抽象 R2/Local + Document 上传 CRUD 下载 8 端点 + Splitter 抽象层 + `process_document()` + 触发端点 + enum 化迁移 0007/0008 + 检索 service + 命中测试端点。详见最近迭代。
  - **v2 方向**：混合检索 / FTS / RRF / rerank / 多向量；切块优化（heading 感知——命中测试已暴露双换行段切分对 list-heavy md 失效，留作自研切块器 A/B 对照案例）；评估体系（Recall@k/MRR + LLM 自动造测试集）。
  - 既有决策：embedding 每库锁一个模型、rerank 先阿里、全文检索先 Postgres 原生 FTS（不够再上 ParadeDB pg_search，不上 ES）、切块默认（递归~512token+50overlap）+ 可配；混合检索/FTS/RRF/rerank/多向量 = v2；文档编辑用自封装 tiptap（后做）。
- **Agent 模块（CRUD + Playground + 工具装配 全打通）**：架构地基见 `docs/architecture.md`（11 节战略 + 附录 A），产品形态（双入口 / 三层资源 / L1-L3 记忆 / @直连 vs 管家）保留为待迭代区。Hybrid Schema（核心列 + jsonb 扩展，AgentConfig 嵌套 schema 强类型契约 Pydantic + `extra="forbid"`）+ 模板层 1+N（1 个可配置 loop 引擎 `general` + N 个 graph 模板首批 0）。**已完成**：后端 5 端点 + 模板层 + LoopTemplate.build() 真实装配（共享 create_agent 工厂 + base_prompt 追加 system_prompt 不覆盖）+ Playground 对话流整片（runtime/runner + route + 前端通用对话层）+ 字段对齐（types/agent.ts + ConfigPanel + AgentCard 嵌套 schema）+ 头像统一默认 gopher 不暴露上传 UI + **工具装配链路全栈（见最近迭代「工具模块第一刀」）**。**接下来候选**：(a) MCP 工具接入（`mcp_tools` 字段 + `langchain-mcp-adapters` 运行时拉远端工具）/ ~~(b) KB-as-tool~~（已完成，见 2026-06-08 迭代）/ (c) 有 key 内置工具的凭据层（抄 Model Provider 那套，Fernet 加密 + 运行时工厂装配）/ (d) workspace 真对话片（chat 层全复用零工作量，仅后端 Conversation + Redis cache-aside）/ (e) **KB-as-tool v2 增强**（hybrid/keyword 模式实装 + KB slug 字段 + 多 KB rerank + 命中测试 UI 加 mode 选择器 + LangChain `create_retriever_tool` 工厂收口）。详情页砍「正式对话」——归 workspace。
- **Workspace 模块（d-1 对话整片完工，剩两个排后小件 → d-2 硬骨头）**：stream 端点 + 落库 + 前端全接真 + 配置面板完成（见最近迭代 2026-06-11）。**排后小件**：(1) 标题异步生成走 BackgroundTasks（lazy 兜底：进对话时若 title=="" 且 message_count >= 2 再补一次，ChatGPT/Claude 同款异步后置）；(2) **3c+ 多会话并发流**——前端 `conversationId → store` 缓存 Map（vanilla store 流循环不挂组件生命周期，切走不杀 store 即后台跑完落库 done；切回复用 store 接着看；后端零改动）。**d-2**：member 招募 + 外层 StateGraph 图壳 + WorkspaceContextMiddleware + state schema 三件套真上（按架构地基阶段 1 → 阶段 2 切换，硬骨头都在 d-2）；**d-3**：@ 路由（mentioned_member_ids 进 body + 输入框 @mention 按真设计重做）+ 视图隔离 + 共享内存。**远期已讨论**：沙箱产物走「本体外置存储 + 消息存引用 + 产物清单注入上下文」（LangChain ToolMessage content/artifact 同款分野），引用天然落在 tool_use 块 result_data jsonb、schema 零改。
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

### 2026-06-11 — Workspace d-1 对话整片：runtime 事件总线 + stream 落库 + 前端全接真 + 配置面板

**后端 runtime 事件总线化（adapter 二元组 + runner sink + 桶）**

- adapter 从「吐 SSE 成品字符串」改为吐 `(EventType, payload)` 原料二元组，SSE 序列化收口 runner 一处；**三元组方案被否**（adapter 翻译+序列化双职责、且 payload/sse 冗余）
- runner 加 `sink: Callable[[EventType, dict], None]` 旁路钩子（keyword-only）：每事件先喂 sink 再序列化（Unix tee 分叉——一份前端一份落库）；`_feed_sink` 兜异常只 log——**旁路（落库）故障不打断主路（用户正看的对话）**；MESSAGE_START/STOP 也喂（collector 从 START 拿 message_id，id 主权在 runner）
- `MessageCollector`（runtime/collector.py）：**只攒不判**——blocks 按 index dict 寻址 + property 出有序 list；**status 判定归端点控制流**（悲观默认 stopped → 自然走完改 done → finally 拼合 saw_error）：MESSAGE_DELTA 每轮模型回合都发不可信、MESSAGE_STOP 断连时到不了——**位置不撒谎，事件会**
- 落库块形态 = SSE 攒平（snake_case 同字段名），不带 UI 态；tool 块 `status: None` = 没等到结局（DB 只存事实不存进行时）

**stream 端点（用户手写，喂口模式）**

- 流程：JOIN 归属校验 → 拉历史快照 → **先落 user**（说出去的话即事实，prepare 400 也不蒸发）→ `AgentSpec.from_jsonb(supervisor)` → 流 → finally `asyncio.shield(persist)`（**stopped 路径恰恰最依赖 finally 落库**——cancel 后裸 await 可能被二次打断，shield 让 INSERT 必然跑完）+ touch updated_at
- **决策 E「存而不喂」**：DB 存完整 blocks（出口1 前端拉历史完整还原），拼 LLM 上下文只回放 text（thinking 是草稿、tool 轨迹吃上下文易带偏；text 已消化工具结果、要旧数据模型会重调工具）；可逆——改喂法零迁移
- `ConversationStreamIn` 无 history 字段：**谁持有历史谁拼**（沙盒前端持→body 送；workspace DB 持→后端拼）；chat-store 加 `sendHistory` 开关对称
- 流式 id == DB id：`MessageAppend.id` 加 `default_factory=uuid7` + service 显式透传（PK 永远 DTO 提供，刷新拉历史 id 不变）
- `from_jsonb` 砍「dict 里翻 template」假能力：盘遍调用方无人需要（supervisor/member/NPC 全是调用方手里有模板 key）→ template 改显式形参、脏数据 fail fast——**用户一句"本来就不需要啊"推翻剔除式修法：不需要的能力不修，直接删**

**前端接真（3a/3b/3c/3d 四步，mock 全退役）**

- 3a：types/workspace 对齐三 Out schema（mock 形态平移进 pages/workspaces/mock.ts 原名保留、组件只改 import 行）+ api/workspace.ts 11 函数 + `conversationStreamEndpoint` helper
- 3b：列表页接真（l-ring + refetch + 卡片成员堆叠降级为管家单标识）；**验收点① 通过**
- 3c：详情页接真（无对话自动建一条保证进来能打字）+ `WorkspaceChat` mount 通用 chat 层 + chat-store 加 `hydrate`（历史灌入，竞态解法 = 历史加载完前不渲染输入框）+ `chat-history.ts` 翻译器（workspace 侧，对称后端「桶通用/翻译在场景」分层）：stopped→completed 安静躺、**tool 无结局→calling 灰色正常展示**（用户改判：不当 error——没失败只是没结局）、inputPreview 用流式同款解析补
- 3d：配置 UI 缺口（用户发现：接口有 UI 没有）→ 右栏「空间配置 ⇄ 产出物」**FlipPanel 3D 翻转共用一块地**（rotateY + backface-hidden 纯 CSS；开关在顶排、默认配置面）+ 管家表单（chat 模型 + system_prompt，保存显式构造 supervisor jsonb 不 spread）+ `supervisorReady` 前置校验链（MessageInput 加 `disabled/disabledHint` 通用扩展，未配模型禁发指路）

**讨论沉淀**

- **多会话并发流（3c+ 排后）**：vanilla store 流循环不挂 React 生命周期——切走不杀 store 即后台跑完落库 done；升级成本仅前端 `cid → store` 缓存 Map，后端零改动（ChatGPT 式体验）
- **沙箱产物（远期）**：本体外置存储 + 消息存引用（天然落 tool_use.result_data jsonb）+ 产物清单注入上下文（d-2 WorkspaceContextMiddleware 的活）；LangChain ToolMessage content/artifact 同款分野
- **协作模式**：后端 runtime/端点用户手写、Claude 一小口一小口喂代码带讲解；中途 Claude 未经批准开工被叫停一次（讨论没结束别动手）；验收统一用户 UI 测（后端 curl 也不替跑）

### 2026-06-09 — Workspace 后端 d-1 前半段：数据层 + 三 entity CRUD + runtime AgentSpec 解耦

**数据层（commit 20504ea）**

- 4 表 model：Workspace / WorkspaceMember / Conversation / Message（迁移 0011 已 apply）
- 关键决策：**supervisor 自带不招募**（存 `workspace.supervisor` jsonb，复用 AgentConfig schema，不进 agents 表）+ `unique(workspace, agent)` 阻重复招募 + Message **三层身份字段**（`role` user/assistant 业界规范 + `sender_kind` user/supervisor/member 业务区分 + `sender_member_id` FK SET NULL 踢人保历史）+ `content` jsonb blocks 对齐前端 chat.ts + `mentioned_member_ids` 冗余 jsonb 给路由用 + `status` 三态 done/error/stopped
- **thread_id = conversation.id.hex 约定映射 LangGraph checkpointer**——业务库 vs checkpointer 状态三分铁律，通过约定关联、不进 schema
- 4 FK CASCADE + 1 FK SET NULL（messages.sender_member_id 唯一 SET NULL：踢人保历史）
- WorkspaceCreate/Update/Out 三 schema，config/supervisor 宽松 dict，强类型 WorkspaceConfig / SupervisorConfig 留下一刀对齐 AgentConfig 范式

**三 entity CRUD（commit ca390e6）**

- Workspace 5 端点 `/api/v1/workspaces`
- Conversation 5 端点 nested `/workspaces/{wid}/conversations`
- Message 只开 **GET 列历史**（写消息走未来 stream 端点；编辑/删 v1 不做——消息是历史事实）
- 归属校验靠 ORM JOIN 一次过（conversation→workspace→user）；`.exists()` EXISTS 校验比 `.first()` 取全行更省
- **MessageAppend service 内部 DTO**——不是 API 契约，stream handler 流完 done/error/stopped 调 `message_service.append()` 落库

**Runtime refactor — AgentSpec DTO 解绑 Agent ORM（commit f1e180f）**

- 抽 `AgentSpec` frozen dataclass 作为 runner 输入契约，只装 `template + config` 两字段（runner 真正需要的全部）
- `prepare_stream(agent: Agent, ...)` → `prepare_stream(spec: AgentSpec, ...)`，runner 不再绑 ORM 实体
- 两 factory：`from_agent(ORM)` / `from_jsonb(dict)`，workspace.supervisor / 招进 workspace 的 member / 临时 NPC 全部能复用 runner 零工作量
- AgentConfig 校验前置到 factory 阶段，runner 假设 spec 合法、不再二次防御（谁创建谁负责验）
- Playground 调用方改 `AgentSpec.from_agent(agent)`，docstring 同步更新

**架构决策修正 — d-1 阶段不上外层 StateGraph 图壳**

- 跟用户架构文档"阶段 1"对齐：外层 StateGraph 可以完全不要，直接 `butler.ainvoke()` 跑
- 当前 supervisor 通过 `prepare_stream(AgentSpec.from_jsonb(workspace.supervisor), ...)` 即可，跟 Playground 走同一 runner
- 外层图壳 + WorkspaceContextMiddleware + state schema 三件套真硬骨头在阶段 2（d-2 招募功能起来时一起装）

**讨论沉淀**

- **标题生成 = 异步后置（BackgroundTasks）而非 graph 前置节点**：业界 ChatGPT / Claude.ai 全异步后置（不阻塞 TTFT + 等首条 assistant 完后总结质量更好 + 失败容错简单）；v1 走 BackgroundTasks，真长任务起 ARQ 时顺手迁
- **DTO vs Schema 边界**：Pydantic Schema 跨 HTTP 边界（需校验 + OpenAPI），dataclass DTO 跨内部边界（service ↔ runtime，不接 HTTP）；AgentSpec 是后者
- **mentioned_member_ids 冗余字段**：text 嵌 `@nickname` 给人看（改名不影响历史），jsonb id array 给程序用（路由 / 反查 / 统计）；Slack / Linear / GitHub 同款双写
- **"CRUD 看起来 low 但是对"**：Anemic Service 是 v1 工程纪律，业务规则真到了再补；真正的肉在 supervisor 调度 / 视图隔离 / @ 路由，那才是 workspace 模块硬骨头

### 2026-06-08 — KB-as-tool 后端整片打通：检索层策略重构 + per-KB tool 装配链路

**检索层重构（`app/services/knowledge/retrieval/` 子包）**

- 策略模式 + dispatch：`RetrievalMode` StrEnum（v1 仅 vector）+ `Retriever` ABC + `RetrievalParams` Pydantic（跨 mode 共用 query/top_k/similarity_threshold/mode）+ `RetrievalResult` dataclass（hits + timings dict，timings key 由具体 retriever 决定）。**新增 mode = 新建文件 + enum 加值 + dispatch 表加行，调用方零改动**。
- `VectorRetriever`：现有 SQL 原封迁过来（pgvector 余弦距离 + DISTINCT ON 按段去重），timings 给 `{embed_ms, search_ms}`。
- `RetrievalService.retrieve(user, kb_id, params)`：调度入口；归属校验 + KB 取 + dispatch + 外圈 `total_ms` 上移调度层统一收口。命中测试 / KB tool / 未来场景共用此入口。`_RETRIEVERS` 类属性 dict + retriever 模块级单例（无状态可共享）。
- 老 `retrieval_service.py` 删；schema `RetrievalTestIn` 也删（跟 `RetrievalParams` 完全等价）；`retrieval-test` 端点 body 切到 `RetrievalParams`、内部走 `svc.retrieve()`、timings dict 解包重组 `RetrievalTestOut`——**老前端零改动同结果同字段**（mode 默认 vector）。

**Tool 层（`app/tools/knowledge_retrieval.py`）**

- `KnowledgeRetrievalTool`：per-KB bound 实例，绑 `kb_id` + `user`，**不进静态 registry**（registry 是 name → 单例 map，KB tool 跨用户跨 KB 多实例无法启动期注册）。`source_type` Literal 父类加 `"knowledge"` 字面量（Pydantic 子类不能扩 Literal，必须父类先加）。
- 实例字段：`kb_id` / `user` / `default_top_k=3`；`model_config = arbitrary_types_allowed=True`（User 是 ORM 实例非 Pydantic 原生类型）。`name` / `description` / `display_name` 故意不给类级默认值——按 KB 动态拼装、构造时必传（docstring 明示，避免读者疑惑"少字段"）。
- `KnowledgeRetrievalInput` 只暴露 `query` 给 LLM，**不暴露 top_k / mode / threshold**——业界标杆（LangChain `create_retriever_tool` / Anthropic / OpenAI Assistants）同款。理由：检索策略是开发者决策不是 LLM 决策，LLM 拍 K 实测比固定值更差。
- `_format_hits`：命中段拼 markdown 给 LLM，`## [N] doc_name(相关度 0.xx)\n\n段全文`，段间 `---`；只返父级段、不返 chunk_text / id（噪音）。

**装配集成（`runner.py` + `playground.py`）**

- `_assemble_tools(cfg, user)` 加 user 形参 + knowledge 来源：`KnowledgeBase.filter(id__in=cfg.knowledge, created_by=user).all()` 一次性 prefetch + filter 顺便归属校验，残留 id 自动过滤（容错，不让残留配置炸 agent）。
- `prepare_stream(agent, request, user)` 加 user 形参往下传；playground route 调时把 `current_user` 传下去（三处耦合一起改，分开做中间状态炸）。
- tool name 规则：`knowledge_<kb.id.hex[:8]>`（满足 `^[a-zA-Z0-9_-]{1,64}$` 正则）；description 拼 `f"检索知识库《{kb.name}》：{desc}。当你需要..."`——LLM 选库就靠这个。

**关键设计决策**

- **每 KB 一 tool vs 单 tool 多入参**：选每 KB 一 tool（业界共识 LangChain / Anthropic / LlamaIndex 全这套）。理由：LLM 吐 UUID 不靠谱、跨库 score 归一化是大坑、LLM 主动选库可串可并、多 tool 噪音靠 `default_top_k=3` 缓解。OpenAI Assistants `file_search` 是单 tool 但靠闭源后端做归一化工程，独立开发者不复现。
- **per-request 实例化是生产级**：tool 是轻量 Pydantic 对象不是 IO 资源；跟"每请求新建 LangChain ChatModel"一个逻辑（runner.py 现有注释明示廉价）；HTTP middleware chain / SQLAlchemy session 同款 per-request 模型。
- **并发隔离三层**：Python coroutine 栈隔离 + service 单例无可变 self 状态 + Postgres MVCC；同 KB 多用户并发 0 问题。但**现有归属模型只允许 KB 创建者用**（filter `created_by=user`），跨用户共享 KB 是 RBAC / sharing 产品决策，不是检索层问题。
- **不加 KB slug 字段**：name 用 `hex[:8]` + description 承担语义路由，YAGNI。真痛触发条件 = KB > 20 + LLM 频繁选错 + 运维要稳定可读 key。
- **timings dict 形态**：用 dict[str, float] 而非强类型 Pydantic——不同 mode timings key 不同（vector 给 `{embed_ms, search_ms}`，将来 hybrid 给 `{embed_ms, vector_ms, keyword_ms, fusion_ms}`），dict + 端点 `.get(key, 0.0)` 兜底最干净。

**端到端验证**：Playground 实测——LLM 主动调 `knowledge_<hex8>` tool、返 markdown 段落 + 相关度，UI ToolUseBlock 正常渲染。

### 2026-06-07 — Playground 整片端到端打通 + 字段对齐 + immer/Zustand 工厂踩坑

**后端补完 runtime / route**

- `runtime/runner.py`：`build_chat_model(ModelSlot) → BaseChatModel`（函数形态；provider_type → LangChain model_provider 映射表，OpenAI 兼容 provider 全走 `"openai"` + base_url 区分上游，仅 Anthropic 走官方协议；凭证 Model 级覆盖优先 fallback Provider 级）+ `prepare_stream(agent, request)` 同步装配（AgentConfig.model_validate + 模板取 + chat_model build + graph build + 拼 messages，**所有可能 raise 的活在此完成、FastAPI handler 接 400 JSON**）+ `run_chat_stream(graph, messages)` SSE 编排（message_start → adapter → finally 兜底 message_stop）。
- 路由 `playground.py`：`POST /agents/{id}/playground/stream` → `StreamingResponse(media_type="text/event-stream")`。route 直接 ORM 查 Agent 内联归属校验（不走 service，service 返 AgentOut Pydantic 不适合 SSE 路径）。挂在 agent 子路由聚合。
- 配套：`templates/base.py` `LoopTemplate.build()` 占位换成真实 `create_agent(model, tools, prompt)`；prompt 合成 = base_prompt（模板出厂底座）+ system_prompt（用户实例特化）**追加**（不覆盖，客服 / 老师等模板场景才不会丢底座）。

**前端通用对话层整片落盘**

- `types/chat.ts` 三层结构（协议层 ApiContentBlock + SSE event payload + RenderBlock UI 状态 + Message union）。命名约定：API 字段 snake_case 透传后端零映射、前端内部状态字段 camelCase，**`UserMessage.content: ApiContentBlock[]`**（不是 string，未来 image 多模态不破坏 schema）。
- `api/chat-stream.ts` `parseSSEStream` async generator（buffer + `\n\n` 切事件 + finally 释放 reader lock）+ `streamChat(endpoint, body, opts?)` 主入口（endpoint 形参注入、Playground / Workspace 通用、AbortSignal 透传）+ 自定义 `ChatStreamHttpError`。
- `stores/chat-store.ts` **Zustand 工厂模式 `createStore` + immer middleware + Context Provider**（详坑 #2）+ 11 case dispatch + `messagesToHistory` 摊平 helper（user 透传 / assistant 把 RenderBlock filter 出 done text block 拼）+ AbortController 内部维护，stop() 立即 UI 反馈 + abort signal 全链路真停。
- `components/chat/` 通用组件套：MarkdownRender（react-markdown + remark-gfm + Tailwind Typography `prose-sm` 14px）+ TextBlock / ThinkingBlock（折叠 + Brain icon + auto-collapse on done）/ ToolUseBlock（4 态图标 + JSON 美化 + 折叠）+ MessageList（ResizeObserver 跟随滚 + 20px 触底容差 + 手势停跟随 + "回到最新" sticky）+ MessageInput（textarea auto-resize + composition 拦截中文输入法 + isLoading 时键变停止）+ ChatProvider Context（vanilla store + useStore hook）。
- `pages/agents/Playground.tsx` 重写：useMemo + endpoint deps（切 agent 重建 store）+ unmount cleanup `store.getState().reset()`。

**字段对齐 = 预期内的字段错位（详坑 #3）**

- `types/agent.ts` `AgentConfig` 嵌套对齐后端 `schemas/agent/config_schema.py`：`models.{chat|stt|tts|vision|image_gen|video}.{id, params}` + `system_prompt` + `capabilities` + `knowledge / tools / skills` + `behavior` + `ui.avatar_url`。
- `ConfigPanel.tsx` form state 仍扁平方便编辑（model_id / knowledge_ids / tool_ids / skill_ids / temperature / top_p / max_tokens），`agentToForm` 从嵌套读 / `save()` 显式构造嵌套不 spread 旧 config（防带入旧 schema 残留）；头像 UI 删色块改静态 `<img src="/gopher-fcb-glass.png" />` 圆形（**P0 不暴露上传 UI、所有 Agent 默认 gopher**）。
- `AgentCard.tsx` 取数同步嵌套、头像同款。`mock.ts` Template 删 `default_avatar_color`。

**三个深坑（新对话直接抄就能避）**

- **#1 immer copy-on-write vs Vue reactive**：旧版 Vue `streaming.value = msg` + `messages.push(msg)` 两引用共享一个 reactive 对象、mutate 一边两边同步；React 移植到 immer 时存独立 `streaming` 字段引用 → immer mutate `s.streaming.blocks.push(...)` 复制 streaming 对象、`messages[N]` 仍指旧、blocks 永远空、UI 完全不渲染。**修法 = 删 `streaming` 字段，所有 dispatch case 在 set 内查 `s.messages[s.messages.length - 1]` 拿 Draft 引用**（流中 assistant 永远是最后一条，语义清晰、无引用分裂）。
- **#2 Zustand 工厂 + Context 标准 pattern**：必须 vanilla store `createStore` + `useStore(store, selector)`（来自 `zustand`）。`create()` 返的 `useBoundStore` 通过 Context 传下来再直接调 `store(selector)` 看似可工作但**React 不识别这是 hook 订阅、state 变化不触发 re-render**。
- **#3 ConfigPanel 字段不对齐**：后端按 spec 改 `AgentConfig` Pydantic + `extra="forbid"`、前端 mock 字段名（`model_id` / `knowledge_ids` / `mcp_ids` / `avatar_color` / `params`）没跟上 → `prepare_stream` 取 agent.config 时 ValidationError 6 项 extra_forbidden 全爆。修：DB 现存 Agent 删了重建 + 前端字段全部对齐嵌套 schema。

**loader icon 演化（产品决策）**

- inline 闪烁光标（▊ char → CSS 矩形圆角）→ 用户指认要消息级 → lucide `Sparkles` + 自定义变速 `animate-[spin_2s_ease-in-out_infinite]` → 用户否决（太垃圾 + 跟项目其他 Sparkles 重合）→ **最终 ldrs `l-bouncy`**（三球弹跳、size=28 / speed=1.2 / brand 墨绿 `#2f6b53`）+ 外层 wrap div `filter: drop-shadow(0 0 5px rgba(217, 119, 6, 0.55))` **暖橙发光做冷暖混色光晕**（ldrs 单 color 限制，混色只能靠外层 CSS filter）。流式中显示 / 完成后不显示等 actions row。

**通用对话层不绑场景（关键设计沉淀）**

- 后端 `runtime/` 包名、`chat_schema.py` 注释、前端 `chat.ts` / `chat-stream.ts` / `chat-store.ts` 命名都刻意避 playground / workspace 场景。workspace 真对话片直接 mount `createChatStore({ endpoint: 'workspaces/.../stream' })` 全复用、零工作量。
- Redis 不引中间态：workspace 持久化走 **PostgreSQL（真源）+ Redis cache-aside**（DB 查询加速、不当 session 短期存储；30min TTL 跨界 + 多 Tab 撞 + 过期不直观）—— cache-aside 标准做法，前端持 history（沙盒）vs 后端 PG 持 history（workspace）两套设计 runtime 层零差异。

**stop() 全链路真停（沉淀）**

- 前端 `ctrl.abort()` → fetch 抛 AbortError → TCP/HTTP 关 → Starlette/Uvicorn 收到 client disconnect → asyncio cancel response task → runner generator 收到 `CancelledError`（**adapter 的 `except Exception` 抓不到 `CancelledError`，3.8+ 是 `BaseException` 直接子类、cancel 信号穿透**）→ langgraph / langchain / openai SDK / httpx 全链路 cancel → 上游 LLM API 收到客户端断开 → 真停（不再吐 token、不再计费 future）。**但已生成的 token 仍计费**（业界限制、ChatGPT / Claude 网页同款）。

### 2026-06-06 — Playground 对话流 P0 核心翻译层（events / schema / adapter）+ CLAUDE.md 第 9 条

**runtime 层立起（`app/agents/runtime/`）**

- `events.py`：`EventType` StrEnum 覆盖 Anthropic 风 11 个事件名（message_start/content_block_*/message_delta/message_stop/tool_use_*/tool_result/error）+ `sse_event(event, data) -> str` 序列化，`json.dumps(ensure_ascii=False)` 中文不 escape。
- `schemas/agent/chat_schema.py`：通用对话契约（不绑 playground / workspace）—— `TextBlock`/`ContentBlock`（P0 union 只含 TextBlock，扩 union 不动上层）+ `HistoryMessage`（role + content: list[ContentBlock]）+ `ChatStreamRequest`（content + history）。content 一开始就走 block 数组形态，避免后续多模态升级时改上层。同时把原 `chat_schema.py` 错放 agent CRUD 内容拨乱反正为 `agent_schema.py`、`__init__.py` 双 re-export。

**adapter.py — LangChain `astream_events(v2)` → SSE 翻译器**

数据结构（高内聚低耦合，可跨 playground / workspace 复用）：
- `SingletonSlot`（dataclass holder，纯数据）：text / thinking 各持一个，index != None ⇒ 块开着。
- `ToolRegistry`：多并发 tool 块三表（chunk_to_block / id_to_block / block_to_id 双向）+ `register` / `release` 原子方法防多表同步漂移；`block_to_id` 反向表保证 on_tool_end 反查 O(1) 而非线性扫。
- `StreamState`：聚合 next_index（跨类型单调） + text/thinking/tools。
- **模块顶部常量集中**：BLOCK_TEXT/THINKING、DELTA_TYPE_*、DELTA_KEY_*、DEFAULT_STOP_REASON、ERROR_CODE_INTERNAL、ERROR_MESSAGE_GENERIC、TOOL_SUMMARY_MAX_CHARS。

调度 / 处理：
- 主入口 `adapt_chat_stream`：dispatch dict + 装饰器登记（`@_register("on_xxx")`）；扩展新事件类型 = 新加一个 handler、主循环零改动。
- 单例块 helper `_emit_singleton_delta` / `_emit_singleton_stop`：text / thinking 共用「如果没开就开 + 发 delta」模式，消除重复。
- 抽取 helper `_extract_text` / `_extract_reasoning`：跨 provider 兼容 `chunk.content: str | list[dict]`（Anthropic / Responses API / 多模态）+ reasoning 双路径聚合（DeepSeek-R1 `additional_kwargs.reasoning_content` + Anthropic extended thinking 在 `content[i].type=="thinking"`）。
- tool 处理 `_emit_tool_call_chunk`：`chunk.tool_call_chunks` 多并发用 `tc.index` 区分，首条带 name+id 才开块，后续 args partial JSON 流式 delta。
- `on_tool_end`：从 ToolMessage.tool_call_id 反查 block 发 tool_result + `_summarize_tool_result`（100 字截断）。

不变式 / 防漂移：
- **唯一关块入口 `_close_open_blocks`**：正常路径（`on_chat_model_end`）和异常兜底共用，避免两处逻辑写差。
- **错误对外脱敏**：`logger.exception` 内部完整 log，对前端发通用文案 `"对话生成失败，请稍后重试"` + `code=internal_error`，防栈 / 路径 / SQL 泄露。
- **兜底自包 try**：关块和发 error 各自 try，generator 二次失败也只 log、不抛出。

**CLAUDE.md 第 9 条**

> 代码默认生产级最终版：每次落盘的首版即架构 / 命名 / 扩展性 / 类型 / 异常一次到位；不分"先简后繁"、不写阶段化占位（P0/P1、# TODO 这版先这样）。小步迭代是任务分段，不是代码风格分段。

**协作复盘（多次返工的教训）**

- 一开始倾向「先简单后扩展」+ 占位话术，被几轮挑战后改掉默认行为模式。
- adapter 重写经历 4 版：极简 bool 状态机 → blocks 字典过度设计 → 修正成单指针 → OO 化（SingletonBlock 类）提议被自我复盘推翻（80 行类换 10 行重复，ROI 负）→ 最终落函数式 + dataclass holder + 模块常量集中。教训：Python 风格倾向轻量 dataclass + 模块函数，不是类层次嵌套；过度抽象比重复更难维护。
- 跨 provider 形态多次违反「不写阶段化占位」原则（`list[dict]` 跳过 = Anthropic 完全不工作），被指认后修正。
- 评价点：评价者点出 4 个真问题（关块漂移、`str(e)` 外泄、兜底二次失败、O(n) 线性扫）全部纳入修正。

### 2026-06-04 — Agent 前端 mock → 真接口全栈接通 + 允许同名资源 + service bug fix

**Agent 前端整片接真（5 端点全栈）**

- `api/agent.ts` 5 函数（list/get/create/update/delete）+ `AgentCreatePayload/UpdatePayload`。
- `types/agent.ts` 重构 —— `Agent` 形状对齐后端 `AgentOut`：核心列（name/description/template）+ `config` jsonb；mock 时代扁平字段（model_id / system_prompt / knowledge_ids / tool_ids / mcp_ids / avatar_color / params）全部下沉 `config`；`Template` 加 `kind: 'loop' | 'graph'` + `disabled?` 占位标。
- AgentsPage 列表接 `listAgents` + ldrs l-ring + refetch on create/delete；mount 一次性拉 chat models 建 `id → display_name` map 传给 AgentCard 避 N+1。
- AgentCard 字段从 `agent.config.*` 派生 + 右上 Loop/Graph KindBadge + 真显模型名（fallback「已选模型」）；标题独占第一行 + badge 挪第二行解决 truncate 挤问题。
- CreateAgentDialog 组装 `AgentCreatePayload(template: t.key)` 调 `createAgent`；模板小卡禁用 disabled 模板（graph 占位不可选）。
- AgentDetailPage 切真 `getAgent` + loading / not-found 双态；agent 作 state，保存成功 `setAgent` 覆盖。
- **ConfigPanel 大重构**：本地 form state + Sticky 顶栏「橙点·有未保存改动」+「保存中…」按钮 + 整体 PUT；`agentToForm` 摊平 / `save()` 时打包回 `config`；`mockChatModels` / `mockKnowledge` 换 `listAllModels({modelType:'chat',enabledOnly:true})` + `listKnowledgeBases()`。
- Playground 字段对齐（`agent.model_id` → `agent.config.model_id`；`avatar_color` 同款）；mock 回复留待对话片接 LLM 替换。
- 抽 `KindBadge` 子组件：Loop = 品牌墨绿 `brand-subtle`，Graph = 灰底虚线（占位感）；4 处统一观感。
- `agent-mock-store.ts` 删除；mock.ts 砍模板池到 2 张（真 loop `general` + 假 graph `__mock__/graph_demo` disabled）+ 删 `mockAgents` / `mockChatModels` / `mockKnowledge`。
- workspaces/RecruitDialog 意外牵连止血：`mockAgents` 内联占位 `AgentLite[]`；`template.behavior_type` 删后按 kind 映射。

**全局允许同名资源（chore）**

- KB / Provider 删 `unique_together = (("created_by", "name"),)` + service 清理 try/IntegrityError + 迁移 0010 `RemoveConstraint` 两条。AIModel / Agent 本就没约束。
- 对齐 ChatGPT custom GPT / Claude Project / Notion 惯例——列表 UI 靠头像 / 描述 / 时间区分，不用 name 唯一兜底。

**Agent service `get_by_id` 笔误**

- `.filter(...).filter()` 返 QuerySet 让 pydantic `model_validate` 当 list 炸；改 `.first()` 跟 update/delete 同款。详情 `GET /agents/{id}` 通。

**协作 / 分工小复盘**

- 后端 service 原归用户写，但用户当场指认让 Claude 直接落盘（重名片那次）——主动权在用户、Claude 提醒并尊重。
- 前端"显式保存按钮 vs 即时落 store"属于产品行为变化，Claude 按推荐默认开干，用户保留推翻权。
- 命名空间踩坑：mock 模板池 key 一开始臆造 `'builtin/general'`，实际后端 registry 是 `'general'`——前端只读 registry 字段、不发明约定。

### 2026-06-03 — Agent 模块后端整片打通 + 模板设计 1+N 重构

**Agent 后端 CRUD 全栈**：`agents` 表（Hybrid Schema：核心列 name/description/created_by/template + `config` jsonb；迁移 0009）；`schemas/agent`（Create/Update/Out，Update 无 template）；`services/agent`（`AgentService` 5 方法，`AgentOut.model_validate` 直转 + 归属隔离 + `get_template` 校验 template 在册 + template 创建后锁死）；`api/routes/agent`（5 端点 `/api/v1/agents`，put 整体更新）。`config` = 行为(loop `{prompt,model}` / graph `{nodes:{...}}`) + 资源(knowledge/tools/skills id) + `capabilities`，全宽松 dict、暂不严格校验。

**模板层 `app/agents/templates/`**：`base.py` 三层基类（`AgentTemplate` 抽象 + `LoopTemplate` 实现共享 build + `GraphTemplate` 留抽象逼子类各写）；**装饰器注册表**（`@register` + `get_template`/`list_templates`，**防环三铁律**：registry 只 import base、模板 import registry 子模块不 import 包、点火放 `builtin/__init__`）；`builtin/general` 一个 loop 引擎。模板存 key 不建表，元数据声明在代码、图代码（build）占位待接 LLM。

**模板设计大重构 k+n → 1+N**（`agent-templates-v1.md` 重写 v1.1）：能力（强制搜索/反思/沙箱）不再是模板、是**实例层可组合开关**（`config.capabilities` + 能力注册表 + 装配器，最终 middleware = 统一层 + 能力层）；retrieval/builder/reflective 从「模板」降级为能力；loop 收成 **1 个可配置引擎**、graph 首批 0。依据 Anthropic「Augmented LLM 基线 + 能力可组合不是分类格子」。能力注册表/装配器/build 全占位、接 LLM 那片做。

**协作**：全局规则加第 4 条「一次只给一口信息」（写进 `~/.claude/CLAUDE.md`）；中途纠正——能力当模板轴是 spec §8 自警的反模式，写真代码前揪出、零成本改正。

### 2026-06-02 — Agent 体系架构地基定稿（`docs/architecture.md`）

基于 deepagents 源码读核 + LangGraph 适配性确认，落 11 节战略 + 附录 A（源码依据带 file:line）。

- **推翻旧工程底座**：`docs/design/agent-module-v1.md` §10–§11（自研 ContextBuilder / Supervisor Mediator / 7 设计模式 / Hexagonal）整段失效。产品形态（双入口 / 三层资源 / L1-L3 记忆 / @直连 vs 管家）保留为待迭代区。
- **新地基核心**：deepagents 是无状态执行核（编图 → invoke），CoCoWork 做外层薄壳 + 跑中 middleware；三接入面（跑前装配 / 跑中 middleware 主体 / 跑后收拢）；两锚点（`workspace_id` + `agent_role`）；状态三分（checkpointer / Store / 业务库 铁律不混）；NPC 永远 2 层不可派生（不挂 `SubAgentMiddleware`），招募走花名册装 subagent、临时 NPC 走 `spawn_from_template` 工具绕构造锁。
- **NPC 形态自由**：手写 `StateGraph`（需固定流程）或 `create_agent`（开放任务）均可——核心横切（视图隔离 + 回写一致性）锚在 Supervisor↔NPC **派活边界**，与 NPC 内部形态解耦。
- **唯一硬骨头**：`WorkspaceContext` middleware 承载视图隔离 + 回写一致性，机制定死、规则待定、不破 cache。演进预算几乎全押于此。
- **三条战略护栏**：① Supervisor 必须走 `create_agent` 体系（禁手写 `StateGraph` 调度图，防 middleware 覆盖盲区）；② NPC 形态自由；③ LangChain 跨 2.x 须先回地基重审。
- **附录 A**：每条地基断言带 deepagents 源码 file:line 出处；LangGraph 适配性 = 无缝（`create_agent` 产物本就是 `CompiledStateGraph`，自研 middleware 走官方 `AgentMiddleware` 协议 + 扩 `AgentState`）。
- **落地状态**：后端 agent 模块仍未起（无 `app/agents/`、deepagents/langchain 未引入 `pyproject.toml`）；前端 mock 切片不动。地基稳后续切片按地基开工。
- **同日修订（结构原则 + 命名规范）**：① 外层薄图改为**默认结构**（每次请求都套，无运行时分支），"按需"的是图内节点填充而非图壳存在——口诀「图壳默认有，节点按需填」；② 弃用「Butler / 管家」别名，全程统一 `Supervisor`，精确指代用「Supervisor 系统 / Supervisor 图」（整个外层图）vs「Supervisor brain / Supervisor loop」（那个 `create_agent` 节点）消歧；③ 「图替换 loop ✗ vs 图包 loop ✓」判别口诀进护栏；④ 派活 A（brain 并行 task）vs B（外层图 Send fan-out）按路径选不全局选、默认全 A；⑤ 强制步骤默认 middleware（`before_model`）、命名节点级审计才升级为外层图节点；⑥ 附录补「图包 loop 源码出处」+「并行+checkpointer 命名空间冲突」已知约束（deepagents 默认路径绕开，给 NPC 配 per-thread checkpointer 时才踩雷）；⑦ 版本号回填 `langchain>=1.2.11,<2.0.0` + `langchain-core>=1.2.18,<2.0.0`。

## 历史摘要
- **2026-06-01 — 知识库片6 全栈 + 收尾增强：RAG v1 收官**：检索 service（用户写，`RetrievalService.retrieval_test` 入口，归属校验 + embedding 模型 + 原生 SQL）+ 端点 `POST /knowledge-bases/{kb_id}/retrieval-test`；SQL 两层（内层 `DISTINCT ON (paragraph_id)` 按段去重每段取最近子块，外层阈值过滤 + 重排 + `LIMIT top_k`）；`{dim}` f-string 拼类型修饰符（DB int 安全）、其余 `$1-$4` 参数化防注入；score=1-余弦距离。schema + 前端切真接口同步。命中测试首次暴露切块问题（双换行段对 list-heavy md 失效，留 v2 heading 感知切块 + 自研切块器 A/B 对照）。**收尾增强**：批量向量化/删除（部分成功语义，`id__in` JOIN + bulk 写避 N+1）+ 检索耗时 pill（`RetrievalTestOut.embed_ms/search_ms/total_ms` 对标 ES `took`）+ 段数展示 + 轮询丢失修复（触发同步置 `status=processing` 解 race）。
- **2026-05-29 — 知识库片5 全栈：处理管线 + 触发端点 + enum 改造 + 前端入口轮询乐观更新**：Splitter 抽象层（`Splitter` ABC + `LangChainSplitter` 包 RecursiveCharacterTextSplitter，v2 自研对照 swap 装配一行）+ `process_document(doc_id)` 入口（解析→双换行切段→切块→批量 embed 100 一批，状态机 status/stage 推进 + try/except 兜底 + 开头清旧 Paragraph FK CASCADE 连带清 embeddings 支持重入）+ 触发端点 `POST .../process`（状态校验 + BackgroundTasks 异步入队）。**踩坑**：三层 `select_related` 嵌套触发 Tortoise 1.x `_fk_setter` 把 UUID 当 model 实例（`AttributeError`），换 prefetch_related 走多条 SQL 独立 _init_from_db 即稳。模型层 enum 化（4 个 StrEnum `KBStatus/DocStatus/DocStage/SourceType` + `CharEnumField`，迁移 0007/0008 几乎 no-op）。前端三点菜单加触发入口 + 轮询 useEffect + 乐观更新解 race（trigger 后父级立即标 processing 修「BackgroundTasks 还没设 status → 轮询条件不成立永不轮」）。**不开事务**：分阶段 save 让前端看到 stage 推进。决策：位运算多任务状态字符串 v1 不学，真要多任务走 JSONB / 子表。
- **2026-05-28 — 知识库片4 全栈：上传 / CRUD / 下载 8 端点 + 前端文档真接通 + R2 download filename RFC 6266**：上传 3 端点（init / passthrough / complete）按 strategy 分流（R2 走 presign 3 步 / Local 走 passthrough 2 步）+ CRUD/download 4 端点 + raw 端点；Storage 扩 `stat_size` 复校真实大小（前端 init 声明的 size 可能撒谎）；MIME 后端定 + R2 presign 钉 Content-Type、前端 PUT 必须带相同 header。前端 `Document` types + 7 api 函数 + **裸 XHR 真上传进度**（R2，避开 axios 拦截器对 R2 空响应误解包、fetch 不支持 upload progress 标准缺口）+ axios `onUploadProgress`（Local）+ Promise.allSettled 并发 + 单文件失败隔离 + 50MB 上限；R2 CORS + Object R&W token 配妥（PUT 成功 body 空是 S3 协议设计）。R2 download filename：`ResponseContentDisposition=attachment; filename*=UTF-8''<encoded>` 塞 presigned URL + sanitize 去引号/换行防 header 注入，RFC 6266 中文不乱码、GitHub/Drive/Dropbox 同款。
- **2026-05-28 — Workspace 模块前端完整骨架（纯 mock）+ KB 检索测试 mock + 卡片三点统一**：types/workspace.ts + workspace-mock-store + 列表页（成员头像堆叠 + 管家皇冠 + 三点删除）+ 详情页三栏（通讯录 240 / 主对话 / 产出物 320，两侧可独立收起，统一容器 `border + overflow-hidden + rounded-lg`）+ 主对话区核心 = `@mention 自动补全 popover`（textarea selectionStart 正则检测 + 候选浮层 + setSelectionRange）+ mock 双轨路由（@某成员 → 那成员答 / 否则管家答） + 招募弹窗两 tab（模板/Agent）+ Conversation 切换条（popover + 新对话）。KB 检索测试 tab 接 mock（query / topK Select / Cmd+Enter 触发 / 6 段递减相似度 mock，后端片6 接入只换函数实现组件不动）。卡片三点位置统一右上角（5 张卡片对齐）+ KnowledgeCard 状态点挪 embedding badge 行 + AIModelCard 启用图标挪类型 badge 旁，删 4 处 translate-y-3 hack 统一 -mt-1 微调。
- **2026-05-28 — Agent 模块前端切片 0 + 路由→tab 自动同步 + 砍正式对话**：types/mock 重写（8 模板 + 5 Agent）+ AgentsPage 三带式 + AgentCard/TemplateCard/CreateAgentDialog + AgentDetailPage 左 ConfigPanel 40 / 右 Playground 60 + agent-mock-store（zustand）；全局机制 `router.subscribe('onResolved')` + `useTabSync` + `useTabTitle` 解决 tab 串台 / 时序竞争（删了 7 处 openTab 双调用）；砍 agent 详情页正式对话改沙盒、正式对话归 workspace。App Shell 高度链 `SidebarProvider h-svh + min-h-0` 锁定。**注意**：本片产物在 2026-06-04 已被「前端接真」彻底重写——Agent 形状对齐 jsonb / ConfigPanel 改保存按钮 / agent-mock-store 删除 / 模板池砍到 2 张。
- **2026-05-26 — Agent 模块设计 spec + admin 用户管理页(mock)**：`agent-module-v1.md`（14 节）+ `agent-module-frontend-v1.md` 定稿；范式 = 工作空间 + 单 agent 双入口、模板/Agent/实例三层分离、@直连 vs 管家双轨、L1-L3 记忆。**注意：工程底座 §10-11（ContextBuilder/7 设计模式/Hexagonal）已被 2026-06-02 架构地基推翻、模板模型又被 1+N 重构，仅产品形态仍有效。** admin 用户管理页 `UsersPage`（mock：表格 + 搜索 + 角色筛选 + 自身行禁用 + AlertDialog）。
- **2026-05-26 — 知识库片4b-1 Document 数据层 + Model URL nested 化**：Document schemas/service 平地起步（`create_pending/list/get/delete` nested 签名 `(user,kb_id,...)`、`storage_key=kb/{kb}/doc/{doc}.{ext}`、删文档先 storage 后 ORM、`_get_user_doc` 一次 JOIN 验归属）；AIModel URL nested 化 `/providers/{pid}/models`（5 CRUD）+ 保留 flat `/models` 跨 provider 查 + `param-definitions`，`ModelCreate` 去 `provider_id`（path 单源）。
- **2026-05-25 — 知识库片4a 存储抽象层**：`app/core/storage/`（`Storage` ABC + R2/Local 双后端 + `STORAGE_BACKEND` 装配）；R2 预签名直传（服务器零出站；egress 收费 / ingress 免费的不对称是关键）+ Local 后端中转；boto3 `@cached_property` 懒加载、同步 IO 全 `to_thread`。
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
