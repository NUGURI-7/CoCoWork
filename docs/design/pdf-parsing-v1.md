# PDF 解析切片（roadmap P1）—— 工作文档

> 状态：**待实现**。设计已定形，本文档随实现回填。
> 创建于 2026-07-21（四家源码调研验证后的规划讨论），2026-07-23 按实测结果与 roadmap 校准。

## 定位

**不做数字。** 两层原因，分开记清楚：

- **检索效果数字**：现有基准是已切好的段，量不了切块策略；也没有 PDF 语料。要出数字得重建整套评测集，成本远超本片价值。
- **解析质量数字**：能测的那部分（pdfplumber / 百度 / MinerU 谁准）量的是三家解析器的水平，**不是本项目的工程产出**；要算还得引入 OmniDocBench 这类带版面真值的标注集。**不做，也不列为交付物。**

耗时是跑三条路时顺手就能看见的（秒级 / 几十秒 / 几分钟），记一笔即可，不当成果。

形态：解析层可插拔（`Parser` ABC）+ 结构化 IR + 标题感知切块。

---

## 三条解析路

| 路 | 实现 | 拿得到什么 | 定位 |
|---|---|---|---|
| **本地轻量** | `pdfplumber`（MIT） | 字号 + 坐标，标题层级靠字号启发式推 | 默认路。**零配置可用**——别人 clone 项目不配任何 key 就能跑 |
| **云端托管** | **百度云文档解析 API** | `type` / `sub_type`(标题层级) / `page_num` / `position` / `polygon`，表格另给 markdown | 结构真实，不用猜。异步接口（提交 + 轮询），走 SAQ |
| **重型对照** | MinerU（本地 CPU 实测 + 官方托管 API） | 版面分析 + 公式 + 表格结构还原完整流水线 | 对照与兜底 |

路由判定：文本层为空或大量 CID 乱码 → 转云端 / MinerU 路。

**云端路只用百度官方 API，不走 MaaS 平台。** 依据见下方实测记录。

---

## 面试清单（架子，准备面试时重新捋）

| 问题 | 答案骨架 |
|---|---|
| **你们 PDF 怎么解析的？** | 解析层可插拔：本地轻量路（pdfplumber 取字号+坐标推标题）+ 云端托管路（百度文档解析 API）+ MinerU 重型路。产出统一 IR 喂给切块器。 |
| **扫描件怎么办？** | 本地路处理不了，走云端。判定靠文本层是否为空或大量乱码 CID——RAGFlow 就是这么触发 OCR 的。 |
| **表格怎么处理？** | 独立成块、转 markdown，不混进正文。表格被打散当普通文本切，检索「表里的数字」必然找不到——Dify 就是直接丢的。 |
| **双栏 / 复杂版面？** | 属版面分析的活，交给云端 pipeline。RAGFlow 用 KMeans 聚类 x0 判栏数再重排，是四家里唯一做了的。 |
| **为什么不自研版面模型？** | 四家里只有 RAGFlow 训了一个（版面检测，YOLOv10 架构 + 自标数据）；OCR 是 PaddleOCR 的 PP-OCRv4、表格结构是 PaddleDetection，都不是自研。它最复杂的 XGBoost 跨页合并已被自己因性能关掉。连它都在往调托管服务靠。 |
| **生产上你会怎么选？** | 解析外包（托管 API），自己守住解析之后那段——IR 与切块。解析能买到，结构保真买不到。 |
| **你踩过什么坑？** | MaaS 平台卖的是**模型**，不是 **pipeline**（详见下方实测）。 |

---

## 设计决策

### D1. IR 带定位信息 —— 已定，且是硬需求

**做「定位信息」通用槽位，不叫 `page`**：

- 叫 `page` 是 PDF 专属，md/txt 永远是 `None`，污染统一抽象；
- 通用槽位则**PDF 填页码，markdown 填标题链**（标题链本就是标题感知切块的产物）；
- 产品上统一体验：命中结果显示「出自第 12 页」或「出自 第三章 > 3.2 检索」。

**这个槽位是 roadmap P4「引用溯源」的上游**——P4 要让 AI 回答的每条结论能点回原文出处，靠的就是它。**解析这一步不存，后面补不回来**，所以不是可选项。

bbox 级高亮：只留字段不实现（需前端 pdf.js 渲染 + 坐标换算）。

> 对照：MaxKB 只给原文件、不给页码——推测理由是多格式统一 + 段落可编辑（编辑后位置对应关系即失效）。取舍成立，但本项目格式面窄、且标题链能覆盖非 PDF 格式，故走通用槽位方案。

### D2. `DocumentBlock` 不建表

内存 dataclass（同 `AgentSpec` / `RetrievalResult`），解析器造、分段器消费，用完即弃。落库仍用现有 `Paragraph`：

- `title` 列五月建表时就留了（注释「段 / 章节标题」），标题感知分段后正好填上；
- 页码走新加的 `meta` jsonb（只对 PDF 有意义，不值得单开一列）。

字段沿用 `runtime/blocks.py` 的 parse-don't-validate：不认识的块跳过不炸。

### D3. 云端解析进 Model 模块，新增 `doc_parse` 类型

**判据不是「它是不是神经网络」，是「是否需要凭证、可替换、被业务引用」**。文档解析四条全中，与 embedding / rerank 同构。

**实证**：RAGFlow 的 `common/constants.py:86` `LLMType` 枚举里就有 `OCR = "ocr"`，与 chat / embedding / rerank 平级；`rag/llm/ocr_model.py` 把 MinerU、PaddleOCR、OpenDataLoader 全注册成 model provider，连 MinerU 这种纯 Python 库也在内；取凭证走 `resolve_model_config(tenant_id, LLMType.OCR, ...)`，与取 embedding 同一套机制。Dify / MaxKB 没有这个分类，是因为它们根本没做外部解析服务。

**待解**：百度要 API Key + Secret Key 两个凭证，而 `Provider` 只有一个 `api_key_encrypted`。可沿用 MCP server 那手法——整包 JSON 后 Fernet 加密。

### D4. 猜字号保留

理由不是效果好，是**零配置可用**：别人 clone 项目、懒得配一堆 key，也能跑通 PDF。做成优雅降级——没配 key 走 pdfplumber 猜字号（结构糙），配了 key 走真结构化。

---

## 实施步骤

| 步 | 内容 | 说明 |
|---|---|---|
| 1 | `Parser` ABC + `DocumentBlock` + txt/markdown 实现，接进 `process_document` | **分段规则照抄双换行，结果与现状完全一致**——抽象先证明自己无害。验证方式：传同一文件两次对比段数与内容（`trigger_progress` 不允许 completed 重跑） |
| 2 | 标题感知分段 | 兑现 v1 遗留缺陷：list-heavy md 挤成一巨段。markdown 的 `#` 是白送的，零启发式 |
| 3 | `PdfParser`（pdfplumber）+ 放开 `.pdf` 扩展名 | 第 2 步的分段逻辑直接复用 |
| 4 | 百度云 API + MinerU 两路 + Model 模块 `doc_parse` | 异步接口走 SAQ（`registry.py` 加 `TaskSpec` → 写 task → `worker.py` 登记） |
| 5 | 定位信息落库（`Paragraph.meta`，需迁移）+ 检索结果透出 | P4 引用溯源的地基 |

**分工**：`Parser` ABC / `DocumentBlock` / 分段策略 / `process_document` 改造归用户写（架构 + service 层）；schema / route / 前端 Claude 落盘；各 `Parser` 实现待定。

---

## 实测记录

### 解码层三个坑，CRLF 最致命（2026-07-23）

v1 的 `raw.decode("utf-8")` 一行藏了三个洞，全部实测确认：

| 坑 | 现象 | 后果 |
|---|---|---|
| **CRLF 换行** | Windows 文档段分隔是 `\r\n\r\n`，其中**并无连续的 `\n\n`** | `split("\n\n")` 整份失效，**文档挤成一段**（实测 3 段 → 1 段） |
| **BOM `﻿`** | 带 BOM 的 UTF-8（记事本默认存法）解码「成功」但多一个不可见字符；`strip()` 去不掉（类别 `Cf` 非空白） | `^#{1,6}\s` 匹配失败 → **整份文档的 H1 识别不出来**；jieba 多出脏 token 污染 tsvector |
| **NUL `\x00`** | 类别 `Cc`，`strip()` 同样去不掉 | **PostgreSQL 的 text 类型直接拒收**，落库失败。MaxKB `pdf_split_handle.py` 有 `content.replace("\0", "")` 即为此 |

**CRLF 比 BOM 严重得多**——它的现象（整份挤成一段）与 v1 遗留的 list-heavy 缺陷**完全一致**，若不先修，第一步「结果不变」的验证根本分不清是谁的锅。

**处理**（全部收在 `_decode`）：`utf-8-sig` 快路 → `charset_normalizer` 探测慢路 → 换行统一 LF → `translate` 剔除不可见字符。**刻意不剔 U+200C ZWNJ / U+200D ZWJ**（构词符与 emoji 连接符，承载语义）；**不动 NBSP / 全角空格**（类别 Zs，`strip()` 管得了，且中文文档里全角空格常是有意的首行缩进，改了即改内容）。

**编码探测的实测边界**：≥122 字节时 GBK / Big5 / Shift-JIS 全部探测正确；22 字节的极短样本会猜错（GBK→EUC-KR，字节范围重叠）。试过两种补救**都更糟**：加 `gb18030` 兜底会**误吞日文**（Shift-JIS 被解成乱码中文且不报错，因 gb18030 覆盖全 Unicode 几乎不失败）；`cp_isolation` 限定候选毫无帮助。**故不补救**——真实文档不会只有 22 字节。

**这类坑的共性**：不可见字符与换行差异让 `^` 锚定、字典 key、精确比较静默失效，而文件 `cat` 出来、编辑器里看、日志里打全都正常。**低难度、高排查成本**。**修在入口而非各下游各自防御**——下游有多少处就要防多少处，且每处都会忘。

### 硅基流动调 PaddleOCR-VL —— 拿不到结构化（2026-07-21）

脚本 `backend/scripts/probe_docparse.py`，PIL 合成测试页（大标题 + 正文 + 带框线表格 + 页脚）。

| prompt | 结果 |
|---|---|
| `"Parse this document."`（自造） | 陷入重复生成，`finish_reason=length`，烧光 16384 token；输出里混着 `<\|LOC_74\|>` 坐标 token 无限重复 |
| `"OCR:"`（官方） | 149 token，文字全对、表格还原成 tab 分隔行列，**但无标题层级、无坐标**，页脚 `-12-` 也当正文吐出 |

**根因**：PaddleOCR-VL 是**元素级识别模型**，官方只给四个 prompt（`OCR:` / `Table Recognition:` / `Formula Recognition:` / `Chart Recognition:`）；页面级解析需 **PP-DocLayoutV2 做版面检测在前**，而 MaaS 平台只托管了后半截。

**结论**：**MaaS 平台卖的是模型，不是 pipeline。** 与 BGE-M3 sparse 那次（`knowledge-rag-phase3.md` §3.2，OpenAI 兼容协议里没地方放 sparse）是同源的坑。要结构化只能走百度官方 API。

### 百度云文档解析 API 返回结构（据官方文档）

异步两步：`POST .../paddle-vl-parser/task` 提交 → `POST .../task/query` 查询。鉴权 API Key + Secret Key 换 access_token。提交 QPS 2 / 查询 QPS 5。

```
layouts: [{ layout_id, text, type, sub_type, page_num, position[x,y,w,h], polygon, span_boxes }]
tables:  [{ markdown }]
```

`type` = text/table/image/title；`sub_type` = 标题层级（需开 `relevel_titles`）；`page_num` 从 0 起；layouts 列表顺序即阅读顺序。**与本片 IR 设计一一对应。**

---

## 已验证的事实（2026-07-21 源码核对，供面试清单引用）

- RAGFlow `deepdoc/server/README.md` 自列模型来源：`layout.onnx` = YOLOv10、`det/rec.onnx` = **PP-OCRv4**、`tsr.onnx` = **PaddleDetection**。所谓「自研 OCR」实为 PaddleOCR 推理栈移植（`operators.py` 的 `DetResizeForTest`/`NormalizeImage`、`postprocess.py` 的 `DBPostProcess`/`CTCLabelDecode` 均为 PP-OCR 结构）。
- `deepdoc/parser/pdf_parser.py:1034` 的 `_concat_downward()` 第二行裸 `return`，XGBoost 跨页合并整段不可达（commit `6d256ff0f`，2025-06-26，*"Perf: ignore concate between rows"*）。
- KMeans 多栏检测是真的、活的（`pdf_parser.py:806` 定义，892 / 1013 / `rag/flow/parser/parser.py:364` 有调用）。
- `deepdoc/parser/paddleocr_parser.py` 默认 `base_url = "https://paddleocr.aistudio-app.com"`，即 RAGFlow 自己在调 PaddleOCR-VL 托管服务。
- Dify（pypdfium2 纯文本、PDF 表格直接丢）/ MaxKB（pypdf + 字号众数，`>2` 给 `##`、`>0.5` 给 `###`）/ LlamaIndex（`Element(type, title_level, table, page_number)`、`MarkdownNodeParser` 的 `header_path`）三家描述均核对无误。
