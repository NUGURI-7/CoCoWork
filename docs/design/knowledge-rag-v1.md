# 知识库模块 + RAG v1 设计方案

> 范围：知识库（Knowledge）模块的后端数据模型、文档处理管线、语义检索、命中测试。
> 不含：Agent / 对话 / 流式（属于后续 Agent 阶段）。本方案为「先简后繁」的第一版，所有进阶能力都以「留口子、不返工」为原则。

---

## 1. 目标与范围

**本期要做的：**
- 知识库 CRUD（支持多库，先全平铺，无文件夹/标签）。
- 文档上传（**仅 MD / TXT 纯文本**）→ 存 R2 → 解析 → 切段 → 切子块 → 向量化入库。
- 语义检索（纯向量），父子块返回：**embed 小子块（搜得准）+ 命中后返回所属整段（上下文足）**。
- 知识库内的「命中测试」面板：输入一句话，看检索出哪些段 + 相似度分数。

**本期不做（见 §9 留的口子）：**
全文检索 / 混合 / RRF / rerank、更深分层（子块再往下切）、多向量（问题/标题向量）、编辑段、文件夹/标签/共享、命中处理方式（直接返回）、按文档单独配切块、换 embedding 模型的重建流程、ARQ 异步、PDF/DOCX 解析。

---

## 2. 关键决策摘要

| 决策点 | 结论 |
|---|---|
| 层级 | 文档 → 段(Paragraph) → 子块（切分动作，**不落表**）；子块下不再切 |
| 检索粒度 | embed 子块，命中后**返回子块所属的整段 `Paragraph`**（父子块） |
| 向量存储 | **不单独建 chunk 表**；`Embedding` 行内存子块文本（`text`）+ 指回段（`paragraph_id`）+ `source_type`（多向量留口子） |
| 多库 | 支持；每库**锁定一个 embedding 模型**，引用 Model 模块的 embedding AIModel |
| 不同维度 | 各库维度可不同；**ANN 索引按知识库分别建**（参考 MaxKB） |
| 检索方式 | v1 仅**语义（向量）**；FTS / RRF / rerank → v2 |
| 文件存储 | **R2**（S3 兼容），保留原件；本地开发可用 MinIO |
| 异步 | v1 **同步**（FastAPI `BackgroundTasks`），管线逻辑独立成 `process_document()`，将来换 ARQ 只改调用处 |
| 切块配置 | **知识库级**一套（默认递归切，chunk_size ~512 token、overlap ~50） |
| 文件类型 | 仅 MD / TXT |
| status | `status`(pending/processing/completed/failed) + `stage` + `error_message` |

---

## 3. 数据模型（4 张表）

> 主键统一 UUID7（`UUIDBaseModel`）+ `TimestampMixin`（与 User/Model 模块一致）。

### 3.1 `knowledge_base` 知识库
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID7 | 主键 |
| created_by | FK User | 所属用户（沿用 Provider 命名） |
| name | str | 名称 |
| description | str | 描述 |
| embedding_model_id | FK AIModel | 锁定的 embedding 模型（Model 模块 type=embedding） |
| embedding_dim | int | 向量维度，建库时随模型锁定 |
| chunk_config | JSON | 切块配置：chunk_size / overlap / strategy（库级一套） |
| status | enum | 库级状态：`ready` / `reindexing`（换 embedding 模型全库重建时用） |
| created_at / updated_at | dt | 时间戳 |

### 3.2 `document` 文档
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID7 | 主键 |
| knowledge_base_id | FK | 所属知识库 |
| name | str | 文档名 |
| file_type | enum | `md` / `txt` |
| size | int | 字节数 |
| storage_key | str | 文件在存储后端的键：S3 后端=对象 key，本地后端=相对路径 |
| char_length | int | 字符数（冗余，展示用） |
| paragraph_count / chunk_count | int | 冗余计数（展示用）；chunk_count = 切出的子块数 = content 向量数 |
| status | enum | pending / processing / completed / failed |
| stage | enum | 挂在哪步：parsing / splitting / embedding |
| error_message | str? | 失败原因 |
| created_at / updated_at | dt | 时间戳 |

### 3.3 `paragraph` 段（父级：展示 / 返回单元）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID7 | 主键 |
| document_id | FK | 所属文档 |
| knowledge_base_id | FK | 冗余，便于过滤 |
| content | text | **段全文——命中后返回给模型的就是它** |
| title | str? | 段/章节标题（可空） |
| position | int | 段在文档中的顺序 |
| char_length | int | 字符数 |
| created_at / updated_at | dt | 时间戳 |

### 3.4 `embedding` 向量（embed / 检索单元；一对多指回段，多向量留口子）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID7 | 主键 |
| knowledge_base_id | FK | 冗余，**ANN 索引/检索按它过滤** |
| document_id | FK | 冗余，删文档级联清理 |
| paragraph_id | FK | **始终有——命中后据此返回整段** |
| source_type | enum | `content`（v1 唯一）/ `question` / `title`（留口子） |
| text | text | **被 embed 的源文本**：v1=切出的子块原文；将来=问题/标题文本 |
| position | int? | 子块在段内的顺序（content 行用；question/title 行可空） |
| embedding | vector | pgvector，列**不锁维度**以兼容多库不同维度 |
| meta | JSON | 元数据 |
| created_at | dt | 时间戳 |

> 设计要点：**不单独建 chunk 表**。子块是「切分产生、用完即弃」的派生物——段一变就整段重切重 embed，数量都可能变、无独立身份、不被谁单独引用——故其文本直接落在 `embedding.text` 上。`embedding` 始终挂 `paragraph_id`（返回单元）。v1 = 每个子块一条 `source_type=content` 的向量；将来加「问题/标题」多向量，只是往这张表**插更多行**（段级、position 置空），不动历史数据。命中测试展示 `embedding.text` 作为「命中片段」。

---

## 4. 文档处理管线

入口函数 `process_document(document_id)`（纯逻辑，v1 用 `BackgroundTasks` 调）：

1. `status=processing, stage=parsing`：从存储后端取文件 → 抽取纯文本（MD/TXT）。
2. `stage=splitting`：
   - 文本按结构/大小切成多个 **Paragraph（段）**；
   - 每个段按 `chunk_config`（size + overlap）切成多个**子块（仅内存中，不落表）**。
3. `stage=embedding`：逐个子块调用本库的 embedding 模型 → 向量 → 写一条 `embedding`（`text`=子块原文，`source_type=content`）。
4. `status=completed`；任一步异常 → `status=failed` + 记 `stage` 与 `error_message`。

> **v1 手动向量化**：上传只创建文档（status=pending），**不自动处理**；用户手动触发「向量化」→ 端点用 `BackgroundTasks` 跑 `process_document` 后立即返回，前端轮询 status。「上传即自动向量化」将来做成库级配置项。

---

## 5. 检索（语义，父子块）

1. 入参：query 文本、目标 knowledge_base、`top_k`、可选 `similarity_threshold`。
2. 用该库的 embedding 模型把 query 向量化。
3. 在 `embedding` 表按 `knowledge_base_id` 过滤，按向量距离（cosine）排序，取候选。
4. 命中的每条 embedding → `paragraph_id` → 取整段 `content`。
5. **按段去重**（同一段的多个子块可能都命中），每段取其最佳子块分数，排序后返回 top_k 段。
6. 返回：段内容 + 分数 + 来源文档（+ 命中片段 `embedding.text`）。

> **实现手法（参考 MaxKB 验证）**：SQL 用 `embedding::vector(dims) <=> $query` 算余弦距离（列不锁维度，查询时 cast 成该库维度）；按段去重用 `DISTINCT ON (paragraph_id) ... ORDER BY paragraph_id, distance`（每段取最近子块），外层再按 `1-distance` 过阈值、排序、LIMIT。

**检索参数**（查询时旋钮，不进表）：`top_k` 默认 5；`similarity_threshold` v1 先不设或设很低。

---

## 6. 命中测试面板

- 知识库详情页内的功能：输入框 + `top_k` 调节 → 调上面的检索 → 列出命中的段 + 分数 + 来源文档（命中片段 = `embedding.text`）。
- **不落库**（即时查询）。
- 是 RAG 检索的第一个消费方——**不依赖 Agent / 对话页**即可端到端验证整套切块+向量化+检索是否好用。

---

## 7. 文件存储（抽象 + 双后端）

- **一层存储抽象**（`save(bytes)→key` / `get(key)→bytes` / `delete(key)`），底下两个后端：
  - **本地文件系统**：写到配置目录（私有数据目录，非对外静态目录）。零基建、不走网络，适合开发 / 简单自托管（需挂持久卷）。
  - **S3 兼容**（R2 / S3 / MinIO）：`aioboto3` 之类，配 endpoint / bucket / key（从旧项目迁）。适合生产 / 多实例 / 高可靠。
- **启动时按 `STORAGE_BACKEND`（`local` | `s3`，默认 `local`）选后端**，实例化一次；service 只依赖抽象。
- 不硬绑 R2 的理由：硬绑 → 别人自托管被迫开云对象存储账号。
- `document.storage_key` 两后端通用（本地=相对路径，S3=对象 key），数据模型不变；**保留原件**以支持重切 / 预览。

---

## 8. 异步演进路径

- v1：`BackgroundTasks` 在 web 进程内跑 `process_document()`，无队列、无 worker。
- 将来：起 ARQ（Redis 队列 + 独立 worker），端点改为「入队」，**`process_document()` 函数体不变**。
- `status` / `stage` 字段已为异步进度建模，UI 轮询逻辑现在就能用，切换无感。

---

## 9. 预留的口子（不返工的关键）

| 能力 | 口子 |
|---|---|
| 多向量（问题/标题） | `embedding` 独立表 + `source_type`，将来插段级行即可（不动历史数据） |
| 更深分层（子块再切） | v1 子块为最小 embed 单元；将来要更深层级再加，`embedding.text` 仍存被 embed 的文本 |
| 全文检索 / 混合 | 将来加 `search_vector`（**可用 Tortoise 自带 `TSVectorField`**，中文先 jieba 分词），叠 RRF + rerank |
| 换 embedding 模型 | KB `embedding_model_id` / `embedding_dim` 可变 + `status=reindexing`，重读段重切重算向量 |
| 异步 | 管线独立成 `process_document()` 函数 |
| 按文档配切块 | `chunk_config` 现在在库级，将来可在文档级覆盖 |
| 文件夹 / 标签 / 共享 | 当前平铺，将来加组织/范围维度 |

---

## 10. API 端点草拟（前缀 `/api/v1`）

- 知识库：`POST /knowledge-bases`、`GET /knowledge-bases`、`GET /knowledge-bases/{id}`、`DELETE /knowledge-bases/{id}`（改名/改配置 PATCH 后补）
- 文档：`POST /knowledge-bases/{id}/documents`（上传）、`GET .../documents`、`GET /documents/{id}`、`DELETE /documents/{id}`
- 段：`GET /documents/{id}/paragraphs`（列表）（编辑段 v1 暂不做）
- 命中测试：`POST /knowledge-bases/{id}/retrieval-test`（query, top_k）→ 段 + 分数

---

## 11. 技术注意事项

- **pgvector**：本期启用扩展（`CREATE EXTENSION vector`），列为第一条迁移。
- **Tortoise + pgvector**：Tortoise **无 pgvector 支持**（无 `vector` 字段、无 `<=>` 等距离算子）→ embedding 列需**自定义 Field**（db type `vector`）+ 相似度检索走原生 SQL（`embedding <=> $query` 排序）。注：Tortoise **自带 `TSVectorField`（TSVECTOR，全文检索用）是另一回事**，留给 v2 混合检索的 FTS，不是嵌入向量。
- **ANN 索引（机制已确认，参考 MaxKB）**：列存不锁维度 `vector`；**按知识库建「部分索引」**——`CREATE INDEX emb_hnsw_{kid} ON embedding USING hnsw ((embedding::vector({dims})) vector_cosine_ops) WHERE knowledge_base_id='{kid}'`；维度用 `vector_dims()` 动态查，向量化后建、重嵌入前 drop。**查询必须用同样的 `::vector(dims)` cast + `knowledge_base_id` 过滤**，否则命中不了索引、退化全表扫描。v1 数据量小可先不建、走 seq scan。
- **>2000 维**：pgvector HNSW 硬上限 2000 维。超了（如 OpenAI `text-embedding-3-large`=3072）→ 让模型降维输出 / 改用 `halfvec`（上限 4000）/ 不建索引走 seq scan。
- **命名约定**：`KnowledgeBase` / `Document` / `Paragraph`(段) / `Embedding`；子块 = 切分产生的文本，存 `embedding.text`，**无独立表**。

---

## 12. 待定 / 后续决策

- **多向量最终要不要**：倾向要（可作为亮点），口子已留，v1 先不建。
- 编辑段、命中处理方式（直接返回）、FTS/rerank、更深分层的具体形态等，进入对应迭代再定。

---

## 13. 实施切片与顺序（小步迭代，每片单独验收）

- [x] **片1 基建**：自定义 `VectorField` + pgvector 扩展（0.8.1 已启用）。存储抽象延后到 **片4 上传**时一并做。
- [x] **片2 数据模型**：4 张表 `knowledge_bases` / `documents` / `paragraphs` / `embeddings` 已建；`embeddings.embedding` 列 = pgvector `vector` 类型。
- [x] **片3 知识库 CRUD**：schema + service + route（`/api/v1/knowledge-bases`，5 端点；service 返回组装好的 `KnowledgeBaseOut` 含 embedding 模型名 + 计数）
- [ ] **片4 文档上传**（拆 2 小片）：
  - [x] **4a 存储抽象 + 双后端**：`app/core/storage/` 抽象基类 + R2（预签名直传）/ Local（后端中转）+ `STORAGE_BACKEND` 装配；详见 §8c
  - [ ] **4b 上传端点 + Document CRUD**：R2 走 presign/confirm 三段式、Local 走 passthrough multipart；列表/删除/下载链接
- [ ] **片5 处理管线**：`process_document()` 解析→切段→切块→embed（手动触发，`BackgroundTasks` 跑）
- [ ] **片6 检索 + 命中测试**：检索 service（`::vector(dims)` cast + `DISTINCT ON` 按段去重）+ 命中测试端点

> 顺序：先 **片1+片2**（地基），验迁移 + 表结构 → 再 3→4→5→6。每片完工：勾选本清单 + 更新 `docs/context.md`。
