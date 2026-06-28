# RAG 检索性能基准 设计与路线 (v1)

> 范围：为 RAG **向量检索**建立一套可复现的**性能 + 召回**基准——量化检索延迟 / 召回随规模（N）的变化，并补齐挡在前面的三块缺口（HNSW 索引 / 批量导入 / 评测脚本）。
> 不含：hybrid / FTS / RRF / rerank 的基准（v2）、parent-child 真实层级效果（需真实长文档线，Multi-CPR 给不了）、多领域横评、并发 QPS 压测（按需后置）、embedding 模型 fine-tune。
> 本文是 `knowledge-rag-v1.md` 的专题延伸，聚焦"检索质量与性能的量化"，不改动既有 RAG 数据模型与检索逻辑。

---

## 1. 目标与范围

**为什么做：**
- 给检索建立**生产基准**（有 HNSW 索引下的延迟 / 召回水位），而不是停留在"能跑"。
- 量化检索的 **scaling 行为**（延迟、召回随向量规模 N 怎么变），作品集可展示深度。
- 顺带补齐三块工程缺口，让"知识库"从"能用"走到"可度量、可调优"。

**本期要做：**
- 把 Multi-CPR 医疗语料灌进库（批量导入入口）。
- 按库建 **HNSW 索引**（partial 表达式索引）。
- 写**召回评测** + **性能统计**脚本（独立，不进产品）。
- 跑出阶段 0–4 的数据（基准 / 无索引对照 / 规模曲线 / 调参）。

**本期不做（见 §9 留口子）：**
- 二次切块（Multi-CPR 段=块，再切会破坏 qrels 对应）。
- hybrid / FTS / RRF / rerank 基准；多领域（电商 / 视频）横评。
- 并发 QPS 压测（locust，按需）；embedding 模型 fine-tune / 横评（阶段 5 可选）。

---

## 2. 关键决策摘要

| 决策点 | 结论 |
|---|---|
| 数据集 | **Multi-CPR 医疗域**（Alibaba-NLP, SIGIR 2022）；MS MARCO/TREC 格式，自带切好段 + 相关性标注 |
| embedding | **硅基流动 `bge-large-zh-v1.5` / 1024 维 / zero-shot**（不 fine-tune） |
| 入库粒度 | passage 已是检索单元 → `Paragraph : Embedding = 1:1`（**段=块**），parent-child 在此退化 |
| 二次切块 | **不做**——会破坏 qrels（标注针对整条 passage）；parent-child 价值留给真实长文档线 |
| HNSW 索引 | 列不锁维度 → **partial 表达式索引**，每库一个：`((embedding::vector(1024)) vector_cosine_ops) WHERE kb_id=...` |
| 建索引时机 | **先灌数据、后建索引**（边插边维护 HNSW 很慢） |
| 性能口径 | **只看 `search_ms`（纯 DB）**，排除 `embed_ms`（网络抖动会污染） |
| 召回评测 | **`ranx`**（或 `pytrec_eval`）算 recall@k / MRR@10 / nDCG——**不自写指标** |
| 评测脚本位置 | `backend/benchmarks/`，**独立脚本、复用检索 service、不进产品** |
| pid 映射 | 入库时保留 Multi-CPR pid（存 `Embedding.meta`），检索结果据此对照 qrels |

---

## 3. 数据集

**来源**：Multi-CPR，`https://github.com/Alibaba-NLP/Multi-CPR`，默认分支 `main`，数据在 `data/<domain>/`（`ecom` / `video` / `medical`），本期取 **medical**。

**格式**（MS MARCO / TREC 事实标准）：
| 文件 | 行格式 | 说明 |
|---|---|---|
| `corpus_split_1~4.tsv` | `pid ⇥ passage` | 语料库，**已切好段**；medical 拆成 4 个 split（单文件过大），合计 ~96 万 passage |
| `dev.query.txt` | `qid ⇥ query` | 测试查询，1000 条（真实自然医疗问题） |
| `qrels.dev.tsv` | `qid 0 pid 1` | 相关性标注（标准答案）：qid 的正确段落 = pid |
| `train.query.txt` / `qrels.train.tsv` | 同上 | fine-tune 用，**zero-shot 暂不下载/不用** |

**落位**：`data/medical/`（仓库根 `.gitignore` 已加 `/data/`，~334MB 不入库）。下载方式 = 直接拉 raw（**不要 git clone 整个 repo**），文件为真实内容、非 git-lfs 指针。

**对应关系（已实测验证）**：`query[i]` ↔ `pid = 30000000 + i`。例：query 2「大人手搓婴儿眼睛红了…」→ pid 30000002「…指甲划伤涂结膜导致出血…」。问题、标准答案、原文三者咬合。

**特性**：corpus 每行即段落级检索单元（无"段→子块"层级）；qrels 针对整条 passage，**故入库 1:1、不二次切**。

---

## 4. 现状与缺口

**已有设施**（勘察 `backend/app/`，主体已生产级完备）：
- **模型**：`KnowledgeBase / Document / Paragraph / Embedding`——parent-child 双层（段=父返回 / 子块=子检索）；`VectorField` **不锁维度**（兼容多库不同维度）。
- **ingestion**：`services/knowledge/document_processor.py::process_document`（解析→切段(`\n\n`)→splitter 切块→分批 embed→入库；BackgroundTasks）。
- **切块器**：`services/knowledge/splitter/`（LangChain `RecursiveCharacterTextSplitter` 包装）。
- **检索**：`services/knowledge/retrieval/vector.py::VectorRetriever`——余弦 `<=>` + `DISTINCT ON (paragraph_id)` 按段去重 + 阈值 + top_k + **`embed_ms`/`search_ms` 分段计时**（已为性能测量埋点）。
- 完整 service / schema / route / 迁移 0005–0008。

**缺口**：
- **Gap1 — HNSW 索引未建**：全 backend 无 `CREATE INDEX ... hnsw`，现检索 = 全表顺序扫描。`VectorField` 列是无维度 `vector`，pgvector 建 HNSW 要求固定维度 → 不能直接建 → 须 partial 表达式索引（§5）。
- **Gap2 — 缺批量导入入口**：`process_document` 依赖①文件已上传对象存储（`storage_key`）②按 `\n\n` 切段 ③splitter 切块——喂不进扁平 TSV，且会丢 pid（召回评测命根子）。须独立批量导入入口（§6）。
- **缺评测脚本**：无召回 / 性能批量评测代码（§7）。

---

## 5. 索引方案（Gap1）

因 `embedding` 列是无维度 `vector`，HNSW 索引须用**表达式 + partial**，每个知识库建一条：

```sql
CREATE INDEX <idx_name> ON embeddings
USING hnsw ((embedding::vector(1024)) vector_cosine_ops)
WHERE knowledge_base_id = '<kb_id>';
```

**要点**：
- **cast 一致性**：表达式 `embedding::vector(1024)` 必须与 `retrieval/vector.py` 的检索 SQL **逐字一致**，否则不命中索引（代码已有注释提醒）。
- **一库一索引**：`WHERE knowledge_base_id=...` 的 partial 形态，对应"一个 knowledge_id 一个 HNSW 索引"的设计意图。
- **参数**：建索引 `m`（默认 16）、`ef_construction`（默认 64）；检索期 `SET hnsw.ef_search`（默认 40）。阶段 4 扫这些参数做召回-延迟权衡。
- **LIMIT 命中**：HNSW 仅在 `ORDER BY <=> ... LIMIT k`（k 不过大）时被 planner 选中；现检索 SQL 带 `LIMIT top_k`，索引建好即走上（无需改检索）。
- **建索引时机**：建库时无数据先不建；**批量灌完后一次性建**（导入流程收尾步，或独立运维动作）。

> 实现（迁移 / service）归用户写——本节只定方案。

---

## 6. 批量导入方案（Gap2）

为预切好的 TSV 语料新增**独立导入入口**（不走 `process_document`），复用既有数据模型与检索逻辑：

**前置**：建一个 `KnowledgeBase`（绑 `bge-large-zh-v1.5` 的 AIModel + `embedding_dim=1024`）；前提是 `AIModel` 里已有该 embedding 模型 + 硅基流动 provider 配妥。

**虚拟文档**：为 4 个 split 建 1~4 个 `Document`（`storage_key` 指向 `data/medical` 本地路径或占位标记），满足 FK + 冗余计数展示。

**逐行映射**：读 `corpus_split_*.tsv` 的 `pid ⇥ text` →
- 建 `Paragraph`（`content=text`）
- 建 `Embedding`（`text=text`，`paragraph` 1:1，`source_type=content`，**`meta` 存 Multi-CPR `pid`**）

**pid 映射（关键）**：Multi-CPR `pid` 存进 `Embedding.meta`（或 Paragraph 冗余字段）→ 检索结果能映射回 pid，才能对照 `qrels` 算召回。**这是召回评测的命根子，不能丢。**

**分批 embedding**：复用 `ModelClient.create_embedding`，BATCH 32~64；硅基流动免费档慢，须**限流 + 重试 + 断点续传**（能中断接着跑）。

**规模档位**：可只导子集（前 N 条）做小档，或全量；规模曲线（阶段 3）按档位分别灌 + 建索引。

> 实现（service / 脚本）归用户写——本节只定方案。检索逻辑零改动。

---

## 7. 评测方法

**召回**（正确性 + 质量）：
- 工具 **`ranx`**（易用，qrels + run → 一行出所有指标）或 `pytrec_eval`（TREC 官方、学术权威）。**不自写指标**（并列/截断/归一化边界条件易错）。
- 流程：遍历 `dev.query` → `VectorRetriever` 取 top_k → 收集命中 pid 组装 run → 对照 `qrels.dev` → 算 **recall@k / MRR@10 / nDCG**。
- 对齐论文 baseline（MRR@10 / Recall@1000）验证没写错（量级一致即可）。

**性能**（延迟 / 吞吐）：
- **只测 `search_ms`（纯 DB 检索）**，排除 `embed_ms`（调硅基流动 API，网络抖动）——否则测的是网络不是索引。
- 批量跑 N 条 query 收集 `search_ms` → `numpy.percentile([...], [50, 95, 99])` 出 **p50 / p95 / p99**。
- **QPS**：并发压测用 `locust`（按需，阶段后置）。

**脚本位置**：`backend/benchmarks/`（独立脚本，import 并复用产品检索 service，不进产品 API）。

---

## 8. 分阶段计划

| 阶段 | 先做什么 | 测什么 | 结论 |
|---|---|---|---|
| **0 打通** | 建库 + 批量导入入口 + 灌 **1 万** + 建 HNSW + 写召回脚本 | 链路跑通 + recall@10 量级对不对 | 证明没写错（召回与论文 bge baseline 同量级） |
| **1 基准** | 灌到 **10 万** + 建 HNSW | `search_ms` p50/p95 / QPS / recall@10 / MRR@10 | "生产基准版"性能水位 |
| **2 对照** | 同 10 万，**禁用索引** | 全表扫描耗时 | 量化 HNSW 价值（复刻 30s→0.5s 故事） |
| **3 规模曲线** | 多档位（1万/5万/20万/50万/96万） | 延迟-规模、召回-规模曲线 | 验 O(log N) 亚线性、找性能拐点 |
| **4 调参** | 固定规模，扫 `ef_search` / `m` / `ef_construction` | 召回 vs 延迟权衡曲线 | 索引该怎么配 |
| **5（可选）** | 换 embedding 模型 / 论文 fine-tuned checkpoint | recall 对比 | 回答"不同模型差距多大" |

核心 = 阶段 0→1→2（基准 + 对照）；深度 = 3→4（曲线，作品集最亮）；5 可选。

---

## 9. 留口子 / v2

- **模型对比**：换 embedding 模型 / 用论文 fine-tuned checkpoint（ModelScope），对比 recall——量化"领域微调的提升"。
- **parent-child 真实价值**：用真实长文档线（PDF / 网页，有真正的"段→子块"层级）演示，Multi-CPR 不适合。
- **并发 QPS 压测**：locust，多请求并发打不同库（多租户形态）。
- **多领域横评**：电商 / 视频域（Multi-CPR 另两域），对应"多 knowledge_id"多库架构。
- **hybrid / FTS / RRF / rerank 基准**：接 `knowledge-rag-v1.md` §9 的 v2 检索增强后再测。
