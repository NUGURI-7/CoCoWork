# 知识库 + RAG — 决策与权衡

> 记录设计阶段的「为什么这么定」「考虑过什么、为什么否掉」「中途反转」。正式 spec 见 [`knowledge-rag-v1.md`](./knowledge-rag-v1.md)。
> 范围仅限知识库 / RAG。Agent 类型选型（deepagents 当能力层、`create_agent` + middleware）、流式（SSE 事件协议）属 Agent 阶段，另文记录。

---

## 1. 做的顺序：知识库 + RAG 先于 Agent / 对话页

- **结论**：先做知识库模块 + RAG，对话页 / Agent 往后。
- **为什么**：RAG 检索的第一个消费方是知识库内的「命中测试」面板（输入 query → 看命中段 + 分数），它不需要 LLM / 流式 / agent loop。所以**不依赖对话页就能端到端验通整套「切块 → 向量化 → 检索」**。对话页是 Agent 阶段的事，不是 RAG 的前置。

---

## 2. 数据模型：从 5 表收敛到 4 表（砍掉 chunk 表）

- **结论**：4 张表，层级仍是 文档 → 段 → 子块，但**子块不落表**，文本存 `embedding.text`。
- 一度设计成 5 表（多一张 `chunk`）。**否掉的理由**：
  - chunk : 向量 = **1:1**（一个子块只产生一条 content 向量）。
  - 多向量挂在**段**上、不挂子块（问题/标题是段级语义），所以即便上多向量，单个子块仍只 1 条向量。
  - chunk **无独立身份**：不被编辑（编辑在段级）、不被独立返回（返回整段）、不被别的实体引用。
  - chunk 是**用完即弃的派生物**：段一改就整段重切重 embed，子块数量都可能变（4→3），且只能机器切、人不手编。
  - → 1:1 + 无身份 + 用完即弃 = 单独建表是过度规范化。
- **单独 chunk 表唯一能换来的好处**：可恢复的分批 embedding（先落 chunk 再分批 embed）。v1 小文件 + 同步 + 切分可重放，不值一张表。以后异步/大文件需要再拆不迟。

---

## 3. Embedding 为什么独立成表（一对多）——一次反转

- **结论**：Embedding 独立成一张表，一对多指回段，带 `source_type`。
- **反转**：最初我建议「向量塞段上、别拆表」，**前提是「一段一向量」——这个前提错了**。
- **真相**（来自旧项目 MaxKB）：**一个段会有多条向量**——
  - 正文向量（每子块一条）
  - 问题向量（给段挂「它能回答的问题」；用户提问是问句，**问句匹问句**比问句匹陈述句命中率更高）
  - 标题向量
  - 全用 `source_type` 区分、全指回同一个段。
- 所以 Embedding **必须**独立、一对多。MaxKB 的 Embedding 单独成表正是为此（是有意设计、不是随意）。v1 只做 content，门留着，将来插行不迁历史数据。

---

## 4. 父子块

- 段(Paragraph) = 父 = 编辑 / 展示 / 返回单元；子块 = 子 = embed / 检索单元。
- **embed 小子块（搜得准）+ 命中后顺 `paragraph_id` 返回整段（上下文足）**。
- 为什么要两级：切太大向量被稀释、切太小丢上下文——父子块两头占。

---

## 5. 切块

- 切块对检索精度**影响极大**（可能比选哪个 embedding 模型还关键）：太大稀释、太小丢上下文、切点烂出垃圾块。
- overlap / chunk_size / 分隔符 / 策略 是**切的配置**，不进表结构；切完每个子块只存 `text` + `position`，overlap 无非相邻子块文本重叠、照存。
- 配置放**知识库级**（整库一套），v1 默认递归切 ~512 token / overlap ~50；文档级覆盖留口子。

---

## 6. 多库 / embedding 模型

- 每库**锁定一个** embedding 模型。**同库不能混模型**——不同模型的向量活在不同坐标系、维度可能都不同、**不可比**（物理约束，不是选择）。
- 跨模型多库挂同一个 agent：不能塞进一次向量搜索，只能**各库分别搜、再合并**。
- **rerank 是「统一度量衡」**：它按「query + 文档原文」算相关度，跟向量怎么来的无关，所以能把来自不同库、不同模型的候选拉到同一把尺子上排。→ **rerank 解锁跨模型多库**，也是多向量 / 跨库这些功能天然依赖 rerank 的原因。

---

## 7. 检索

- **v1 纯语义（向量）**。
- 混合（v2）= PG 原生 FTS（字面匹配）+ 向量（语义）两路 → **RRF**（不用模型、按排名位置合并两个榜的便宜公式）→ **rerank**（模型精排）→ top_k。RRF 糙而便宜、rerank 准而贵，可叠可单用。
- **vs MaxKB**：MaxKB 混合评分是「两个分数直接相加」（`1-distance + ts_similarity`），比 RRF 糙、易被量纲大的一边主导——我们走 RRF，不跟它。

---

## 8. 文件存储：抽象 + 双后端（默认本地）

- PG 大对象能存（旧项目就是），但**非生产标准**（撑大 DB、备份重、混业务数据）。
- **关键顾虑**：硬绑 R2 → 别人自托管被迫开云对象存储账号，门槛高。
- 解法：**一层存储抽象**（save/get/delete），启动按 `STORAGE_BACKEND` 选后端——**本地文件系统**（默认，零基建、不走网络、适合开发/自托管）/ **S3 兼容**（R2/S3/MinIO，生产/多实例/高可靠）。
- 本地盘 vs PG 大对象：本地盘同样零基建，却不会撑大 DB——零基建场景本地盘更干净。
- `document.storage_key` 两后端通用（本地=相对路径，S3=对象 key），数据模型不变。
- 本地盘风险（容器需挂持久卷、多实例不共享、无内置冗余）→ 扩容/高可靠时切 S3，抽象已就位。

## 8b. v1 手动向量化

- 上传文档只创建记录（status=pending），**不自动处理**；用户手动点「向量化」才跑管线（`BackgroundTasks`）。
- 「上传即自动向量化」将来做成库级配置项；先手动，逻辑都在 `process_document()`，切自动只改触发处。
- 影响：`document.status` 在 v1 就有实义（pending = 已传未向量化）。

## 8c. 上传/下载方式：R2 预签名直传 + Local 后端中转（实施时确定，2026-05-25）

- **默认后端调整**：§8 抽象层做完后，默认从「local 默认」改成 **`STORAGE_BACKEND=r2`**——R2 桶已就位，生产形态优先；Local 仍保留给离线开发。
- **上传/下载方式（不对称）**：
  - **R2**：上传走**预签名直传**（客户端 → R2 直连）；下载走**预签名 GET URL**（用户直链）
  - **Local**：上传走**后端中转**（multipart POST），下载走后端 `read` + StreamingResponse
- **不对称的根因**：本地文件系统没有「对外暴露临时直传 URL」的概念，必须经后端中转。接口上用 `supports_presigned: bool` 标志 + 基类默认抛 `NotImplementedError` 表达；业务层按标志分流。
- **核心理由（服务器出站才是收费方向）**：
  - 服务器**出站(egress)收费**、入站(ingress)免费；R2 出口免费。
  - passthrough 上传的「后端 → R2」那一程是**服务器出站**（≈ 文件大小 / 每次上传）；presigned 把文件流完全踢出服务器路径，零出站。
  - 同理下载：预签名 GET 让用户直接从 R2 拿，避开「后端 → 用户」的服务器出站。
  - **易踩的认知坑**：「RAG 反正后端要处理拉回来 → presigned 省得有限」——**错**。处理时是入站(免费)，passthrough 上传是出站(收费)，**入站和出站不对称**，presigned 省的是真金白银。
- **复杂度代价（认领）**：R2 需 3 个端点（presign + 客户端 PUT + confirm）+ 孤儿对象清理（R2 桶生命周期规则 + 应用层定期对账）；前端按 `storage.supports_presigned` 分流两套上传路径。
- 详细推导、流量费用表、能力标志的 pattern → `notes/backend/storage-upload/notes.md`

---

## 9. 异步：v1 同步，留门

- **BackgroundTasks**（同 web 进程内跑、无队列无 worker）vs **ARQ**（Redis 队列 + 独立 worker 进程，≈ 轻量异步版 Celery）——**二选一，不是都用**。BackgroundTasks 轻活够用但重活抢资源、进程重启就丢；ARQ 重活扔给 worker、任务持久、可扩容。
- v1 用 BackgroundTasks；逻辑独立成 `process_document()`，将来换 ARQ **只改调用处**（端点改入队），函数体不变。`status` / `stage` 已为异步进度建模。

---

## 10. pgvector 维度 / 索引

- 列用**不锁维度的 `vector`**，才能同表装不同库、不同维度的向量（MaxKB 的 `VectorField.db_type` 返回纯 `'vector'`）。
- **不锁维度的列上怎么建固定维度 HNSW（MaxKB 已验证）**：建**部分索引**，索引建在表达式 `(embedding::vector({dims}))` 上、带 `WHERE knowledge_id='{kid}'`，每库一条；维度用 `vector_dims()` 动态查。**查询必须同样 cast（`::vector(dims)`）+ 同样过滤**才命中索引，否则退化全表扫描。向量化后建、重嵌入前 drop。v1 数据量小可先不建、seq scan。
- **>2000 维**：pgvector HNSW 硬上限 2000。超了（OpenAI 3-large=3072 等）→ 模型降维输出 / `halfvec`（上限 4000）/ 不建索引。
- Tortoise **无 pgvector 支持**（无 `vector` 字段、无 `<=>` 算子）→ embedding 列自定义 Field + 相似度查询走原生 SQL（`<=>`）。**别混**：Tortoise 自带的 `TSVectorField` 是 `TSVECTOR`（全文检索），留给 v2 FTS，不是嵌入向量。

---

## 11. status 设计

- v1 简单：`status`(pending/processing/completed/failed) + `stage`(挂在哪步) + `error_message`(为啥挂)。
- MaxKB 那种「多任务复合状态字符串」（embedding / 生成问题 / 同步 各占一位）先不用，等以后多任务再升级。

### 11.1 v1 简化点 → 生产级升级触发条件（2026-05-29）

v1 处理管线刻意走最朴素路径，主要为对齐当前场景（单任务、单进程、无并发、文档量级小）。下面 4 个简化点都不是技术不会，是**当前场景不需要**。升级时按各自触发条件单独切片实施，不预先堆。

| v1 简化 | 现在为啥不做 | 升级触发条件 | 升级方案 |
|---|---|---|---|
| **单字段 status + stage**（不分任务类型） | v1 只有 embedding 一条流程，无其他任务并行 | 加多任务（rerank / 自动生成假设问题 / 同步等任意 2 个起） | **走 JSONB 或 `document_task` 子表**（参考 Agent 模块 Hybrid Schema），**不学 MaxKB 位运算字符串**（自描述性近零、加任务要改解析、并发不安全） |
| **无分布式锁** | `BackgroundTasks` 在 web 进程内单线程跑，不会同 doc 并发 | 切 ARQ 多 worker、或同 doc 可能被并发触发 | Redis 分布式锁（`SET NX EX`），lock key = `process:doc:{id}`，TTL > 单文档最长处理时间 |
| **无任务中断检查** | v1 没暴露「取消」给用户、且单文档处理时间短（秒级） | 暴露用户「取消」按钮、或处理时间拉长到用户会想中断的量级（分钟级 +） | `process_document` 各阶段前 `await Document.get(id).only("status")` 查 `status == 'cancelled'` 即抛 `CancelledError`；状态机加 `cancelled` 终态 |
| **全量 in-memory 处理段 / 子块** | v1 限 50MB md/txt、段数百级、子块数千级，内存压力可忽略 | 解 PDF/DOCX 后单文档段数 10万+、内存撑不住 | 流式处理：段循环里产出子块就批量 embed + insert 一批，hold 时间窗口控制；状态机加段级进度（`paragraph_done_count`） |

**统一原则**：每条升级都是「**加新东西**」而非「**改老结构**」，v1 状态机字段（`status / stage / error_message`）+ 表结构（Paragraph/Embedding）保持不变，向上兼容。

**反模式提醒**：别在 v1 阶段为了"以后好升级"提前引复杂度（状态机库、Redis 锁、子表、流式 generator 都不要）。当前最大风险不是"将来重构难"，是"现在堆复杂度导致代码读不懂、改不动、bug 难定位"。

---

## 12. 易混点：命中测试 ≠ 命中处理方式

- **命中测试**：知识库内的测试面板，输入 query 看命中段 + 分数，**不生成答案**。v1 要做。
- **命中处理方式**（MaxKB 的 optimization / 直接返回 + 相似度阈值）：**回答时**的行为（命中高相似度段时直接返回原文、跳过 LLM），属 **Agent / 对话阶段**，v1 知识库不碰。
- 两者一度被混为一谈，这里钉死区分。

---

## 13. 片5 分块实施取舍 + v2 对照路径（2026-05-28）

### 13.1 v1 用 LangChain 作 baseline 跑通 + v2 自研对照（不当永久依赖）

- **解析**：`path.read_text(encoding='utf-8')` 直接读 md/txt（v1 白名单仅 md/txt，无 PDF/DOCX 等脏格式，**零 loader 依赖**）
- **切块**：`langchain-text-splitters` 子包的 `RecursiveCharacterTextSplitter`
- 仅引该子包（独立轻量），**不引全套 `langchain`**
- 抽 `Splitter` 抽象基类，业务代码（`process_document`）只依赖接口；v2 替换 = 改装配一行、不动业务
- chunk_config 默认值：chunk_size=512 chars / overlap=50 chars / strategy=recursive / unit=chars

### 13.2 为啥 v1 用 LangChain 而非直接手搓

- **对照实验更硬**：v1 baseline = 业界标杆 LangChain，v2 = 自研超越版；这套对比比"自己 v1 朴素 vs 自己 v2 优化"有说服力得多——面试里能讲"我评估了行业标准、发现局限、做了针对性优化"，体现工程判断力而非体力
- **v1 跑通快**：分块逻辑不卡壳、不调边界 bug，时间转头投到检索评估（片 6）和 multi-agent（含金量更高）
- **简历可信度高**：项目里**真实用过 LangChain**，被问"你用过 LangChain 吗"时有底气
- 父子块设计（Paragraph + Embedding 分层）已经覆盖了"层级分块"亮点，分块算法精调收益不大、对照实验收益更大

### 13.3 LangChain RecursiveCharacterTextSplitter 已知局限（认领、准备对照）

- **语义盲目**：不识 markdown 结构（heading / 代码块 / 表格全混着切）
- **中英文混排不友好**：按字符算 chunk_size，一个汉字 ≈ 1.5–2 token，实际上中英文 chunk 大小不等价
- **跨块断裂**：完整论点 / 代码块可能被切两半
- **overlap 是补丁**：加 overlap 本质是承认切割策略不够好、用冗余救场

### 13.4 v2 自研对照路径

- **切换 trigger**：
  - 必要条件：片 6 检索评估体系跑起来、产出第一份 baseline 数据
  - 强制条件：**投简历前**必须换掉，不留 LangChain 在核心
- **优化项（逐项 A/B 对照）**：
  1. **md 结构感知**：按 heading 切段、保留章节上下文
  2. **token-based 切块**：装 tiktoken、`chunk_config.unit="tokens"`
  3. **多向量索引**：每段加 `source_type=question` 假设问题向量 + `source_type=title` 标题向量（表结构已留口子）
  4. **语义感知切块**：用 embedding 相似度判断邻句是否属同语义段
- **评估指标**：召回率@k / MRR / 命中率（量化对比）
- **评估数据集**：human-labeled `(query, 期望命中段)` 对（可借 §13.4.3 的"问题向量"文本反向当 ground truth）
- **切换后**：从 `pyproject.toml` 移除 `langchain-text-splitters` 依赖

### 13.5 实施层面保障"可替换"

```python
# app/services/knowledge/splitter/base.py
class Splitter(ABC):
    @abstractmethod
    def split(self, text: str, config: ChunkConfig) -> list[str]: ...

# app/services/knowledge/splitter/langchain_impl.py
class LangChainSplitter(Splitter):  # v1
    ...

# app/services/knowledge/splitter/cocowork_impl.py
class CocoWorkSplitter(Splitter):  # v2 自研
    ...

# 装配（硬编码、不入 env——splitter 不是部署变量）
splitter: Splitter = LangChainSplitter()  # v1 → v2 改这一行
```

- 业务代码只 `from app.services.knowledge.splitter import splitter; splitter.split(...)`，**不感知实现**
- v2 切换 = 改一行装配 + 移除旧依赖、零业务改动

### 13.6 PDF / DOCX 等复杂格式何时加 loader 库

- v1 白名单仅 md/txt → 不需要 loader 库
- 将来加 PDF/DOCX 时单独决策：候选 `pypdf` / `pdfplumber` / `unstructured`
- 选库标准：单一职责（只做格式解析、不带分块逻辑）、轻量、不抢自研叙事
