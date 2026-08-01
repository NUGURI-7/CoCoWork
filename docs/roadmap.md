# CoCoWork Roadmap

> ## ❄️ 本文档已冻结（2026-08-01），内容原样保留、不再更新。当前路线见 [roadmap/current.md](./roadmap/current.md)。
>
> 冻结时的已知偏差：总览表里 **P1 文档解析、P5 沙箱未勾，但实际已于 07-29 / 07-30 完工**；
> P3 只完成前半（Compress B），P6 已降级为「只跑一遍验证、不进程序」，P7 已砍。
> 结算后的真实状态一律以 `current.md` 为准。
> **仍值得回看的部分**：各片的「已定」小节（取舍依据与源码实证）、P7 节的方向未定案警告、以及文末挂账里的外键索引实测。

> 覆盖当前阶段（约 10 天）的开发序列。核心架构已成型，本阶段补齐能力闭环上的缺口，让产品从「核心跑通」走到「完整可用」。
> 维护规则：每片完工后在此勾掉，要点并入 `docs/context.md`；本文件只保留未完成项与仍然有效的取舍。

## 产品定位

**顶层交互单元是 Workspace（多 agent 协作空间），不是单个 agent。**

同类平台（Dify、Coze 等）的一个 App 对应一个 agent 或一条 workflow，搭好后发布出去供人使用；本项目的一个 Workspace 是一支团队——可招募成员、由 supervisor 派活、支持用户 @ 直连某成员，成员共享同一条对话与上下文。**一句话的差别：同类平台让你搭出一个 agent，CoCoWork 让你组建一个 agent 团队。**

**不走画布编排。** 低代码平台的核心形态是拖节点画流程；本项目走「声明引用 + 后端持有拓扑 + LLM 运行时自主调度」——分工由 supervisor 当场决定，不由人预先画死。这与 subagent / 多智能体自主协作的方向一致。

**这条定位决定后续切片的服务对象**：记忆、执行详情、上下文压缩，服务的都是「团队」这个单元，而非「一个 agent」——它们的设计取舍（中性摘要全员共用、视角化历史重写、按成员泳道隔离）只有在团队语境下才成立。

## 阶段目标

一条链路每一环都有实现：**文档进得来 → 处理扛得住 → 过程看得见 → 对话记得住 → 回答可追溯 → 智能体干得了活 → 存储换得掉**。

## 总览

| # | 切片 | 规模 | 依赖 |
|---|---|---|---|
| P1 | 文档解析层（PDF / 多格式） | 3-4 天 | 设计稿见 `docs/design/pdf-parsing-v1.md` |
| ~~P2~~ | ~~异步任务业务迁移~~ ✅ 2026-07-23 | — | 未等 P1，提前做掉 |
| P3 | 记忆系统 v1 | 2-3 天 | Compress B 数据层已就位 |
| P4 | 引用溯源 | 1-2 天 | P1（定位信息来自解析 IR） |
| P5 | Skill 执行 + 沙箱 | 2-3 天 | 设计稿见 `docs/design/skill-sandbox-v1.md` |
| P6 | VectorStore 抽象 + Milvus | 2 天 | —（不可裁） |
| P7 | Agent 执行记录 + 观测服务 | 2 天 | 全部前序（**越晚做数据越多、越有意义**） |

> **贯穿全程的一条约束**：实现 P1-P6 各片时，顺手把耗时与 token 这类数字算出来记下（至少打日志）。P7 才回头补埋点意味着要把所有链路代码重翻一遍找插入点；提前留下，P7 就只是「把已有数字接起来」。

---

## P1 · 文档解析层

**现状**：只收 md/txt。设计稿已定形态——`Parser` ABC + 结构化 IR + 标题感知切块。

**内容**
1. `Parser` ABC 与 `DocumentBlock` IR 字段落定（沿用 `runtime/blocks.py` 的 parse-don't-validate：不认识的块跳过不炸）
2. 定位信息做成通用槽位，不叫 `page`——PDF 填页码，markdown 填标题链。**这是 P4 引用溯源的上游，解析这步不存后面补不回来，非可选项**
3. **三条解析路**（抽象层的价值由多后端并存来证明）：
   - `pdfplumber` 本地轻量——字号 + 坐标推标题层级，处理有文本层的原生 PDF。**零配置可用**（clone 项目不配 key 即可跑）
   - **百度云文档解析 API**——返回 `type` / `sub_type`(标题层级) / `page_num` / `position`，结构真实不用猜；异步接口（提交 + 轮询）走 SAQ。**不走 MaaS 平台**（硅基流动实测只拿得到纯文本，见设计稿实测记录）
   - **MinerU**——版面分析 + 公式识别 + 表格结构还原的完整流水线，作为重型对照路
4. 路由判定：文本层为空或大量 CID 乱码 → 转云端 / MinerU 路
5. 表格独立成块转 markdown，不混进正文
6. 标题感知切块（一并解决 v1 遗留的「list-heavy md 挤成一巨段」）
7. 接进 `process_document` 管线 + 扩展名白名单 + 前端状态

**完成判据**：传一个含表格与双栏的 PDF，走完解析 → 切块 → 向量化，命中测试能显示「出自第 N 页」或「出自 某章 > 某节」；三条路各跑通同一份文档。

**已定**
- **本片不做数字**。检索效果数字：无 PDF 语料、无量切块策略的评测口径。解析质量数字：能测的部分量的是三家解析器的水平、不是本项目的工程产出，还得引入 OmniDocBench 这类标注集，**不做也不列为交付物**。耗时跑的时候顺手可见，记一笔即可，不当成果。
- bbox 级高亮只留字段不实现。
- 云端解析进 Model 模块、新增 `doc_parse` 类型（实证：RAGFlow `LLMType` 枚举里 `OCR` 与 chat/embedding/rerank 平级，连 MinerU 这种纯 Python 库也注册成 model provider）。
- **MinerU 走「本地实测 + 生产托管」双轨**：本地 CPU 模式（指定 pipeline 后端）跑通一次即可，模型约 3-5GB、10 页纯文字文档约 2-5 分钟；生产路径调官方托管 API（mineru.net，有免费额度），不在服务器上扛 GPU 部署。包名已从 `magic-pdf` 改为 `mineru`。
- 选型立场保持不变：默认路仍是轻量 + VLM 托管，MinerU 作为重型对照与兜底。依据是 RAGFlow 自身也在调 PaddleOCR-VL 托管服务，且其自研的 XGBoost 跨页合并已因性能问题被自己关闭（`pdf_parser.py:1034` 裸 return）。**接进来是为了有实测依据地做这个判断，而不是推翻它。**

---

## ~~P2 · 异步任务业务迁移~~ ✅ 2026-07-23

已完工，要点见 `docs/context.md` 迭代 2026-07-23。**后续切片需要知道的两条**：

- **新增异步任务的三步**：`app/tasks/registry.py` 加一条 `TaskSpec`（必填 `timeout`，SAQ 默认 10 秒）→ 写 `app/tasks/<域>_task.py` 实现 → 在 `worker.py` 的 `functions` 登记并重启 worker。入队一律 `await <SPEC>.enqueue(**kwargs)`，kwargs 走 JSON 序列化、UUID 要转 str。
- **worker 进程不经 FastAPI lifespan**：数据库、日志、以及日后的埋点初始化都得在 `worker.py` 的 `startup` 里自己做（P7 埋点会再撞一次这个坑）。

---

## P3 · 记忆系统 v1

**现状**：Compress 层 A 已完成；层 B 数据层（`ConversationSummary` + 迁移 0015）已落地未提交，service 未做；无跨会话记忆。

**内容**
1. **Compress B service 收口**：封存触发（阈值取 API usage 上报）+ 链式吸收（上一行摘要 + 新封消息 → 新行）+ 拼上下文时「摘要 + 近 N 轮视角化原文」
2. **跨会话长期记忆**：可编辑记忆块（用户画像 / 偏好，常驻上下文）+ 检索式历史召回

**分层参考 Letta**：core block（可编辑常驻）／ archival（向量检索）／ recall（历史消息搜索）。轻量实现即可——Dify 的记忆只有一个 token buffer 文件。

**完成判据**：长对话的 input_tokens 曲线在封存点下折且 prompt cache 命中率不崩；新会话能带出上一会话沉淀的用户偏好。

**已定**：中性摘要一份全员共用（视角化只发生在近段原文的读时改写）；摘要落独立表跨轮复用以护 prompt cache；checkpointer 只当暂停现场保存器、永不当历史存储。

---

## P4 · 引用溯源

**内容**：检索结果携带定位信息回传 → 回答中标注引用 → 前端可点开原文块；prompt 侧约束「只依据检索内容作答，无依据时明说」。

**完成判据**：KB 问答的每条结论都能点回原文出处；检索不足时模型明确表示无依据，而不是编造。

**依赖**：P1 的 IR 定位槽位。

---

## P5 · Skill 执行 + 沙箱

> **方案已定稿（2026-07-24）：`docs/design/skill-sandbox-v1.md`**（23 条决策，每条附源码依据）。
> 本节只留取舍摘要，细节与依据一律看设计稿，不在此复述。

**定位**：做 Skill 的**执行能力**，不做 Skill 聚合站。

**内容**
1. `skills` 独立表（DB 存元数据 + 对象存储存 zip 本体，复用 `storage` 抽象）+ 上传 / 导出
2. `BaseSandbox` 子类（**唯一要写的核心件**）：填 `execute()` + `upload_files()`，其余由 deepagents 基类派生
3. skill 清单自拼进 system prompt（**不用 `SkillsMiddleware`**，它在 agent 启动时就扫目录、与懒启动冲突）+ `FilesystemMiddleware` 那 7 个工具接到沙箱 backend，**仅挂了 skill 的 agent 才装**
4. 一次性 Docker 容器：一次完整回复借还一个，**LLM 首次调工具才懒启动**，`docker exec` 跑命令，完了 `docker rm`
5. `/workspace` 按文件同步回对象存储（key = `sandbox/{workspace_id}/{相对路径}`），`/tmp` 用 tmpfs 即弃
6. 加固：`--read-only` + `--user nobody` + `--memory 256m` + `--cpus` + 专用 docker network + 拦 `169.254.169.254`
7. `sandboxd` 独立进程（`uv run sandboxd`，唯一持 docker.sock）+ `SANDBOX_ENABLED` 三层降级
8. 抽象层留远程执行机 / E2B / 阿里云 FC 的实现位，本片不做

**完成判据**：一个带脚本的 Skill 能被 agent 调用、在容器内执行、产物回传，宿主机无副作用；新开一个对话，agent 能自己发现并接着用上次留在 `/workspace` 的文件。

**已定**（三条容易走回头路的）
- **Skill 不是函数签名**：不走 `assemble_tools`，走「name+description 进 system prompt + 通用文件/shell 工具执行」。五家源码无一例外。
- **agent 循环不搬进沙箱**：只有 OpenHands 是那一档，而它卖的就是「一台机器」；Dify 的 agent 循环也在服务进程里（沙箱只跑 shellctl）。额外买到的仅故障隔离与多租户配额。
- **工作区状态绑 workspace，不绑对话、不绑容器**：workspace 才是持久实体，对应 Letta 绑 agent / Dify 绑 `agent-<agent_id>`。容器一次性、状态活在对象存储。

---

## P6 · VectorStore 抽象 + Milvus

**内容**
1. `VectorStore` ABC（对齐既有 Splitter / Storage / Parser 的抽象风格）+ pgvector 实现平移
2. Milvus 实现——**Lite / Standalone / Distributed 三档共用同一套 client API**，故一个实现即可覆盖，抽象层不为部署形态分叉
3. 按知识库配置选择后端
4. **复用既有 benchmark 跑双后端对照**：同一份语料、同一批 query，出召回与延迟对照

**完成判据**：同一个知识库换后端重建索引，检索结果与既有基准一致；双后端对照数字入档 `benchmarks/FINDINGS.md`。

**已定**
- 排在末尾是因为无前置依赖、可吸收前序延期，**但不是可裁项**——本阶段要落地。
- 开发与集成用 **Milvus Lite**（`pip install pymilvus`，零部署、本地文件持久化）。**三档部署共用同一套 client API，故 Lite 已足够支撑抽象层实现与选型判断**，数据可用官方 CLI 迁到 Standalone。
- **Standalone 列为可选加餐**：它才是真实部署形态——Milvus 本体 + etcd（元数据 / 服务注册）+ MinIO（对象存储）三件套，官方标最低 8GB 内存（官方亦已计划移除这两个外部依赖）。仅在跑双后端对照实验时起一次，跑完可删；本机吃紧就挪到服务器（规格见 `docs/infra.md`）。跳过它不影响本片交付，只是少一组对照数字。
- **内存差异的根因写进答案**：Milvus 是内存常驻的搜索引擎（collection 需显式 `load`，HNSW 图索引随机访问、落盘即失速），架构上同类是 Elasticsearch 而非 PostgreSQL；pgvector 蹭 PG 的 buffer pool，内存不足只是变慢而非失败。真正吃资源的是 C++ 的 Knowhere 引擎（内含 Faiss / Hnswlib / Annoy），Go 只是协调层。
- **诚实预期：当前规模（万级段落 / 百万级向量）大概率测不出显著差异**——pgvector 的适用区间是千万级向量以内，Milvus 的主场是十亿级。若结论确实是「这个规模上没差别，换库的理由不是性能」，**那就是本片的结论，照实记**。这与 rerank、hybrid 两次否决式结论同一形态：能说清「什么时候不该换」比只会夸新组件更有说服力。

---

## P7 · Agent 执行记录 + 观测服务

**排在最后是刻意的**：本片价值在「跨执行回看」，需要前六片先跑出数据；早做只会面对空表。另一条更硬的理由——**现在埋点等于埋在会变的代码上**：P1 加解析器、P3 加记忆、P5 加 Skill，每片都往 runtime 加新调用路径，早埋要回头补 N 遍，等结构定了一次埋完是一遍的事。

> ### ⚠️ 方向未定，第二阶段再启动（2026-07-23）
>
> **本片的「观测」半边尚未定型，读到这里不要重新推导——已经绕过一整轮了。** 当前状态：
>
> - **已排除**：接现成 SaaS tracer。理由是用户实际用过、判定信息组织方式不符合需求；且「装个 SDK」在面试里没有可讲的内容。**不要再提议这条。**
> - **倾向未定案**：OTel 标准埋点 + 现成后端（Jaeger / OTel Collector 一个容器即可，非「需要一堆基础设施」）；业务侧仍保留 `agent_runs` 表，两者靠 `trace_id` 关联而非合并存储。**自建 OTLP 后端 + 瀑布图 UI 暂不推荐**——多出的工作量主要是前端画时间轴，与 agent 能力无关。
> - **待办**：用户先自行了解 OTel 再定方向。**这块缺用户这道审核关卡时，本文档的推导不可靠**（同日实测）。
> - **本片真正指向的问题是「静默失败」**：agent 出事时不抛异常、状态码全是 200（检索返回 0 条 → 照样编；工具异常被编排层吞掉；token 上限撞在工具调用中途；上下文三轮前就污染了）。日志和堆栈对这类失效完全无能为力——这才是 JD 里「链路监控 / 执行链路追踪」指向的东西，不是 P95 曲线。

### 三层分工（对照 Dify 源码——它三层全做，但手段完全不同；本项目只做中间那层）

| 层 | 关注 | 业界做法 | Dify 对应 | 本项目 |
|---|---|---|---|---|
| **系统层** | QPS、P95 / P99、错误率、资源 | 应用埋点导出，展示交给 Prometheus / Grafana / APM，**不自建 UI** | `extensions/otel/` 整包 + `ENABLE_OTEL` / `OTLP_*` 配置 | **不做**（无基础设施则无价值） |
| **LLM 链路层** | 单次执行展开、哪步慢、烧多少 token | **自建执行记录 + 详情视图** | `WorkflowRun` / `WorkflowNodeExecutionModel`（+ `core/ops` 可选接 7 家 tracer） | ✅ **本片主体** |
| **业务层** | 会话数、token 成本、满意度 | 产品统计页，给平台使用者看 | `controllers/console/app/statistic.py` | 不做（产品功能，后置） |

**判据（防止什么都往项目里塞）**：**该能力是否已有成熟通用的外部工具能无缝替代？**
- **是** → 暴露标准接口接进去，别自建。系统指标即此类——自写监控页面是重复造 Grafana，且必然做不过。
- **否** → 自建。LLM 单次链路展开即此类——形态与产品深度耦合，外部工具能做但要求把数据发出去、且交互形态不匹配。

### 本片范围

1. **执行记录落独立表** `agent_runs`：`user_id` / `conversation_id` / `started_at` / `duration_ms` / `status` / `total_input_tokens` / `total_output_tokens` / `steps` jsonb / `error`。`steps` 是数组，每项一步（类型、名称、耗时、token、错误）。索引建在 `(user_id, started_at)`。**写入异步、不阻塞响应**——复用 runner 既有的 `sink` 旁路（Unix tee），步骤在内存攒、流结束时一次落。
   > 曾考虑挂在 `Message` 的 jsonb 字段上（MaxKB `ApplicationChatRecord.details` + `run_time` 同款形态）。**改独立表的理由：要做按用户/按时间的聚合，独立表直接 `group by`，挂 jsonb 得先展开。**
2. **独立观测进程** `cocowork-observe :8001`：**只读**连库（独立只读数据库用户，物理上写不坏数据）+ 共享 `SECRET_KEY` 验 JWT + 仅 admin + 不暴露外网。三个只读端点：执行列表（筛选）、单次执行详情、按天聚合。
   > **独立进程的理由是部署边界，不是性能**——可单独关停、不暴露外网、挂了不影响业务。（性能理由在本项目规模上不成立，别当说辞用，会被追问流量量级。）
3. **前端复用现有 React 应用**：加一个路由、`axios` baseURL 指 8001。不单独起 vite 项目——多一套构建部署不值。
   **信息密度自己把关**：首页只放四个数字 + 一条趋势；列表一行一次执行（时间 / 耗时 / token / 状态）；**步骤明细只在点开详情后才出现**。Langfuse 那种把详情摊在首页是反面教材。
4. **检索管线与 worker 补埋点**：检索把已算出的分段指标显式落出来（模式分支、候选池召回量、`rerank_ms`）；SAQ worker 不经 FastAPI lifespan，初始化要单独做（与「worker 日志掉黑洞」同一个坑）。
   > **顺带评估 SAQ 自带监控 UI**（`saq/web/starlette.py`，`saq_web()` 返回 Starlette 子应用可直接 `Mount` 进 FastAPI，含队列总览 / 任务详情 / 手动重试 / 中止）。**当时刻意没接**（2026-07-23）：它与本片的执行详情**形态相同、数据源不同**，先挂上去等于埋两个长得像的监控入口，届时要合并或删一个。做本片时一并定：是并进自建面板，还是挂它当队列专用视图。注意它**默认无鉴权且带写操作**（重试 / 中止），要挂必须先套上本片的「JWT + 仅 admin」中间件。
5. **benchmark 回归化**（改脚本，不算新模块）：每次改动检索代码后跑一遍、结果入档、指标随版本可比。

**不做**
- **HTTP 接口耗时落库**：高频低价值，写放大 + 数据量爆炸，属于用错工具。生产上这类走 Prometheus 预聚合直方图或 APM 采样。
  > **判据（可复用）：低频高价值事件才落库（agent 执行记录），高频低价值指标必须走指标系统预聚合。**
- **Prometheus / Grafana / APM / OTel 导出**：都要外部基础设施才有价值，个人项目没有。应用侧该输出的（结构化 JSON 日志 + 请求 ID 全链路）已完成。
- **分布式链路追踪**：单体架构、无跨服务调用，不适用——是「不需要」而非「不做」。
- **业务统计页**（会话数 / token 成本 / 满意度）：属产品功能，本阶段不做。
- **Langfuse**：已接通、配 key 才生效，留着零维护，不再投入。

**完成判据**：观测服务能列出近期执行、点开看到每步耗时与 token、按天聚合出失败次数与总花费；主服务挂掉不影响观测服务。

**已定**
- **业界一致做法（源码核实）**：严肃 agent 产品一律自建执行记录，外部 tracer 一律是可选集成。Dify 自建 `WorkflowRun` / `WorkflowNodeExecutionModel` + `core/ops` 并排接 7 家 tracer；**RAGFlow 更彻底——把 Langfuse 做成产品内可配置集成**（`langfuse_service.py` + `langfuse_api.py`，由终端用户填自己的 key），自身另有 `UserCanvas` / `Task` / `API4Conversation` 执行记录；OpenHands 的 `event_store`（三种存储后端 + webhook 订阅）本身就是产品核心。**没有一家把自己的执行详情外包出去。**
- **不宣称「可回放」**：`steps` 只存耗时 / token / 摘要，重跑需要完整 prompt 与工具参数，是另一个数据量级。除非真存了，否则不提 replay——面试追问「怎么跑」会露。
- 埋点收口在 runtime / service 单点，业务层不散落调用。

---

## 本阶段明确不做

| 项 | 理由 |
|---|---|
| RBAC / 多租户 | 能力已在别处覆盖，此处重复建设无增量 |
| 模型微调 | 与平台定位无关，不进本产品 |
| Skill 聚合站 / 市场 | 不自建分发平台。**但上传入库 + 导出在 P5 范围内** —— 从外部聚合站下载的 skill 包能传进来直接用，这是 skill 的价值前提 |
| 生成端评测 | 检索端基准已有，生成端留待后续 |
| 多 @ 并发 | 需 SSE 多路复用 + 前端 N 气泡，中型切片，单 @ 已够用 |
| ES / 自定义词库 / 图谱 | 永久挂账，需要时再评估 |
| 画布式工作流编排 | 「声明引用 + 后端持有拓扑」的既有决策不变 |
| 定时触发 | SAQ 已具备条件、成本低，随时可插，不占本阶段排期 |

## 待定

- **语音（ASR / TTS）**：浅链路（录音 → ASR → 现有 chat → TTS）约 2-3 天，产品完整度收益明确；实时双工（VAD、打断检测、首字延迟优化）是独立项目量级，两者之间没有中间地带。本阶段不排期，视 P1-P7 收尾情况再定。
- **对话多模态输入**（传图提问）：成本很低（messages 里加 image block），可作零碎时间插入。

## 挂账（想起来了就记着，不排期）

### 外键列普遍缺索引（2026-07-24 实测）

Tortoise 的 `ForeignKeyField` **默认不建索引**（只建外键约束）。全库 23 个 `*_id` 列里 **22 个没有 B-tree 索引** ——
唯一有的是 `workspace_members.workspace_id`，且它是搭 `unique(workspace, agent)` 复合索引前导列的便车。
（`embeddings.knowledge_base_id` 看似有，实为 HNSW partial 索引的 `WHERE` 条件，B-tree 查找用不上。）

**这是 PostgreSQL 特有的坑**：MySQL InnoDB 会自动给外键列建索引，PG 不会。

**级联删除是数据库级行为，会被这个拖累**（2026-07-24 实测确认）：
- Tortoise 发出的是**真实 DB 约束** —— 22 个外键全带 `ON DELETE` 子句（CASCADE / RESTRICT / SET NULL），
  级联在 PG 内部由触发器完成。**与 Django 不同**：Django 的 `on_delete` 是 ORM 模拟（Python 侧发多条 DELETE）。
- PG 的级联触发器执行的就是 `DELETE FROM child WHERE fk_col = $1`。`EXPLAIN` 实测（`embeddings` 23368 行）：
  `document_id` / `paragraph_id` / `knowledge_base_id` 三列**全走 Seq Scan**（cost 1341.91）。
  即删一个 document 要全表扫两万多行，且**每删一个父行扫一遍**。
- **只慢不错** —— 正确性无影响，所以一直没被察觉。

**热路径 / 大表那批已补** ✅（2026-07-24，迁移 0018）：`messages.conversation_id`、
`paragraphs.document_id` / `.knowledge_base_id`、`embeddings.document_id` / `.paragraph_id` / `.knowledge_base_id`、
`documents.knowledge_base_id`、`skills.created_by_id` —— 8 个。
实测 cost 1341.91 → 8.30。**规矩已写进 `docs/context.md` 开发注意事项：新建 `ForeignKeyField` 一律显式 `db_index=True`。**

**仍欠着**
- `conversations.workspace_id` —— 该补，但 `conversation_model.py` 当时正被 P3 会话占用，跳过了
- 各表 `created_by_id`（providers / agents / knowledge_bases / mcp_servers / workspaces）、
  `ai_models.provider_id`、`provider_model_catalog.model_id`、`workspace_members.agent_id`、
  `messages.sender_member_id`、`conversation_summaries` 两列 —— 行数少，不疼

**几乎不疼的**：各表的 `created_by_id`（用户自己的资源，行数很少）、`ai_models.provider_id`、`provider_model_catalog.model_id`。
`conversation_summaries` 的两列暂时也不疼（P3 刚落地、数据量小），但它随对话增长，日后归入上一档。

**补法**：model 上加 `db_index=True` 后生成一条迁移即可；大表建议 `CREATE INDEX CONCURRENTLY`（要走 `ops.RunSQL`，且不能在事务里）。
**不急**：当前数据量下测不出差别，属于「知道欠着」而非「现在要还」。
