# 跨轮回放协议 —— 问题诊断（2026-07-30）

> **这份文档目前只有「问题」和「影响面」，没有决策。** 决策等真做那一刀时再补。
> 每条事实标注了来源：**实读代码**／**实测**／**转述（未核实）**。

---

## 0. 一句话

**喂给模型的历史里只剩下「描述」，没有「事实」** —— 工具调用被压平成一行痕迹，
工具结果一个字都不回放，子 agent 的执行过程整段跳过。
两个看起来毫不相干的 bug 是同一个病根。

---

## 1. 现状（实读代码，2026-07-30）

`app/agents/workspace/view_context_assembler.py`：

| 位置 | 行为 |
|---|---|
| `_render_tool` | 非 `task` 的块 → `〔{actor} 调用了工具 {name} → {status}〕`，**`result_data` 一个字不进** |
| `_render_tool` | `task` 派活块是唯一例外 → 带 `result_data` 回放（成员产出算内容，保留是对的） |
| `_render_blocks` | `if b.subagent: continue` —— **子 agent 的执行过程整段跳过** |
| `build` 末尾 | 所有历史消息一律包成 `HumanMessage(f'<msg from="X">…</msg>')`，连角色都抹平了 |

**数据是全量落库的**（实读 `app/agents/runtime/collector.py:105-106、134-135`）：
`status` / `result_summary` / `result_data` 三件套都存了，前端展示读的就是这份。
**丢失只发生在「喂给模型」这一侧** —— 这一点决定了这一刀做得成：原料不用补采。

---

## 2. 两个症状，一个病根

### 症状 A：答不出上一轮的工具结果

用户问「刚才搜到的那个价格是多少」，历史里只有 `〔我 调用了工具 search → 成功〕`，
模型答不出来。（**转述**，2026-07-30 另一会话发现）

### 症状 B：supervisor 空手编造派活（本次实测，证据确凿）

第二轮用户说「把它改成折线图」，supervisor 吐出一整段：派活给成员、成员返回、
交付路径、`<artifacts>chart.svg (3KB)</artifacts>` —— **全是编的**。

数据库实测：

| 查的东西 | 结果 |
|---|---|
| 用户发消息 → supervisor 回复 | **间隔 10 秒** |
| 这一轮的 `tool_use` 数量 | **0 个** |
| 产物表里对应的行 | **没有** |
| 正文里含 `<artifacts>` | **True**（模型自己写的） |

两条铁证：

- 它声称交付到 `/outputs/**019fb29e**-6b6c-…/chart.svg`，而这个 message_id
  **数据库里根本不存在**（真实的是 `019fb29c` 与 `019fb2a1`）。
- 它写 `chart.svg (3KB)`，真实产物是 **3598B = 3.5KB**。数字都对不上。

---

## 3. 根因

把 supervisor 第二轮看到的历史还原出来：

```
好，我来把销量数据画成柱状图。先派活给 Loop。

〔我 派活给 我的通用 Loop#019f0d9b：… → 完成〕
我的通用 Loop 返回：
（成员那段话）

<artifacts>chart.svg (3.5KB)</artifacts>
```

成员那一轮真实发生的 **14 个工具调用**（`write_file /tmp/data.json`、
`execute bar.py --out …`、8 次 `edit_file`）**一个都不在里面**。

> **在它看到的历史里，「干活」这个动作根本不存在，只剩下动作的文字描述。**
> 那段历史里没有任何一部分是「外部给的」—— 从头到尾都是它自己写出来的文本。
> 照着再写一遍，在它的世界观里完全自洽。

对照 notes §36：真实的 tool call 在 API 层是**独立的结构化字段**，模型仿不出来
（仿出来就是真调用）。**一压平成文本，它就从「平台解析的通道」掉进了「模型可写的通道」。**

**这也解释了为什么 prompt 禁令挡不住**：`〔…〕` 与 `<artifacts>` 两条禁令都写了，
照编不误 —— 禁令改变不了「它只见过这一种样本」这个事实。

---

## 4. 影响面

### 4.1 上下文体积

工具结果回放后历史涨得快。业界做法是**靠压缩和 offload 管体积，而不是直接丢弃**
（Letta / Claude Code / deepagents 跨轮都全量保留 —— **转述，未核实源码**）。
我们现在这个做法比业界激进。

**2026-07-30 查证（LangChain 官方文档，非源码）—— 上面那条转述要修正**：
deepagents 并非无条件全量保留，它有一道 offload：

| | deepagents 的实际行为 |
|---|---|
| 触发 | 单个工具结果超 **20,000 token** |
| 上下文里留什么 | **文件路径引用 + 前 10 行预览** |
| 完整结果去哪 | 落到 configured backend（不删，只是移出活动上下文） |
| 模型要看怎么办 | 用 `read_file` / `grep` **自己读回来** |

其他 harness 同款形态：保留输出的**头尾**若干 token，完整输出落盘，模型按需读。

**关键区别：业界处理大结果的手段是 offload，不是转摘要。**
offload 无损、纯机械、零 AI 调用，原文随时取得回；摘要有损、要烧一次调用，
而且**摘要仍然是「描述」不是「事实」**——按 §3 的根因，它治不了症状 B。

来源：<https://docs.langchain.com/oss/python/deepagents/context-engineering>、
<https://www.langchain.com/blog/the-anatomy-of-an-agent-harness>

### 4.2 层 B 压缩 —— **窗口已经用掉了，判据踩着这一刀写死**

原记录是「层 B 判据取主道**第一次**模型调用的 `input_tokens`，理由正是本轮工具往返
下一轮不进历史」。**2026-07-30 当天层 B 切片 1-2 已实装并提交，判据最终取的是
「最后一次」** —— 正是踩着「这一刀会做」这个前提：

| commit | 内容 |
|---|---|
| `d2ce1e4` | `ConversationSummary` 表 + 迁移 0015（已 apply）+ `Conversation.context_tokens` |
| `8d8135b` | OpenAI 家族开 `stream_usage` + `_on_chat_model_end` 发 `message_delta(usage)`（**只主道**） |
| `b979db1` | `collector._absorb_usage` 覆盖写取最后一次 + 端点落库 + 6 条单测；**实测 `context_tokens` 0 → 5534** |

取最后一次的理由：它含本轮全部工具往返，而工具结果**将要**全量进下一轮历史，
所以它就是下轮进场历史的规模。

> **反过来说：这一刀不做，层 B 的判据就是错的。** 若维持「工具结果只留一行痕迹」，
> 最后一次会虚高十几倍（实测量级：第 1 次 8K vs 第 10 次 140K，而下轮真实历史约 9K），
> 每轮都会误触发压缩——烧一次 AI 调用、还把不该压的历史压掉。
>
> 依赖关系已写进代码：`collector._absorb_usage` 的 docstring 标明「若改回痕迹回放，
> 要改成只认第一次」，`tests/test_usage_accounting.py::test_collector_keeps_the_last_usage`
> 是这个假设的哨兵。

**另一个实测数据点**：一句话的空对话，`context_tokens` 地板是 **5534**（系统提示 +
工具定义 + 花名册的固定开销，历史几乎不占）。切片 4 定压缩阈值时要算上这层地板，
不能按「历史多长」拍脑袋。

### 4.3 压缩的频率与体验

历史涨快后，压缩从「低频兜底」变成「高频功能」。v1 的阻塞式压缩（用户等几秒）
是否还能接受要重估，可能得提前上异步。

### 4.4 视角化要分叉

- **自己发起的** tool call → 可以还原成 `AIMessage(tool_calls=…)` + `ToolMessage(…)`
- **别人发起的**（成员之间）→ 不能，塞成结构化模型会以为是自己调的，
  而且它根本没有那些工具
- **`<artifacts>` 标注** → 没有配对的 tool_use，走不了这条路；
  只能靠「独立一条消息 + 角色是 API 字段模型伪造不了」硬一档

**硬约束**：`tool_use` 必须严格跟上 `tool_result` 且 id 对得上。
而现在已存在非完成态（`_STATUS_LABELS` 里的「中断」），中断的调用没有 result，
直接塞进去 **API 会报错**，得专门处理 —— 这是压平方案当初白捡的便宜，改回去就得自己付。

---

## 5. 待议（不下结论）

回放粒度三档，各有代价：

1. **全量回放 `result_data`** —— 与业界一致，上下文涨得最快
2. **回放 `result_summary`** —— 字段已有，折中；但「摘要」本身仍是描述不是事实
3. **按体积分档** —— 小结果全量、大结果转摘要或 offload

另一个正交的选择：**要不要恢复结构化**（`AIMessage`+`ToolMessage`）
还是仍走文本、只是把结果带上。前者才治得了症状 B，后者只治症状 A。

### 5.1 第 3 档的两个分支不同级（查证 + 实读代码，2026-07-30）

第 3 档写的「大结果**转摘要或 offload**」，这两个不是并列选项 —— 按 §4.1 的查证，
业界只走 offload 那支，转摘要没人这么干（理由见 §4.1 末段）。

**但 offload 成立有一个硬前提：模型必须能把原文读回来。** deepagents 靠
`read_file` / `grep`，我们**没有** —— 层 A 挂 `FilesShelfMiddleware` 时明确
「只声明 state 的 files 字段供 offload 存档，**不引入任何文件工具**」
（**实读** commit `e57a2f3`）。

> **没有读回工具，offload 就退化成有损截断** —— 一个「看着像标准做法、
> 其实照样丢信息」的东西。

好消息是原料不用补采（§1 已确认 `result_data` 全量落库），读回工具就是
按 `tool_use_id` 查一条 DB，跟 `app/tools/artifact_fetch.py` 同一套路。

所以这一档的完整形态是**三件套**，缺一不可：

| | 内容 | 落点 |
|---|---|---|
| 1 | 小结果（阈值以下）全量进历史 | `_render_tool` |
| 2 | 大结果留「预览 + `tool_use_id` 引用」 | `_render_tool` |
| 3 | `read_tool_result` 工具，模型凭 id 读回全文 | `app/tools/` 新增 |

阈值取多少未定（deepagents 用 20,000 token，但那是单 run 内的尺度，
跨轮回放该更严还是照搬，需要拿真实对话量一量）。

### 5.2 决策（2026-07-30 用户拍板）

**做 §5.1 的完整三件套，不接受降级版。** 只做 1+2 会得到一个「看着像标准做法、
其实照样丢信息」的东西，那正是最不该交付的形态。

被**否决**的理由，记下来免得下次重新捡起：

| 曾提出的理由 | 结论 |
|---|---|
| 「全量回放能吃到 prompt cache，痕迹回放没命中」 | ❌ **算账后不成立**。缓存命中价约 1/10：全量回放下轮 141K（140K 命中）≈ 15,000 等效；痕迹回放下轮 9K（8K 命中）≈ 1,800 等效 —— **痕迹回放仍便宜 8 倍**，省 token 的效果远大于缓存折扣。全量回放不是为了省钱 |
| 「改协议后压缩变高频，v1 阻塞式撑不住，得先上异步」 | ❌ 用户否掉：上下文基线本来就大，增量的相对比例没那么夸张，推不出「必须异步」 |

**真正成立的理由只有两条**：① 症状 A + B（§2）是实打实的功能缺陷；
② 层 B 判据已经踩着这一刀写死了（§4.2）。

> 顺带澄清一个**真实但归因不同**的缓存问题：跨轮缓存命中率低的主因是**视角化换人**
> —— 换一个应答者，历史整个重渲染（「我」变了），前缀从第一个字就不同，缓存全失效。
> 这是「一份原文 N 个视角」的固有代价，跟工具结果回不回放无关，这一刀也治不了它。

---

## 6. 这一刀的定位

**不是 issue**（issue 目录装的是「有价值但可以一直不做」的）。
它是一个已确诊的设计缺陷，两个独立症状、影响面已摸清。

**2026-07-30 更新：那个「会关上的时间窗口」已经用掉了** —— 层 B 切片 1-2 落地时
判据就按「这一刀会做」写死了（§4.2）。所以它从「趁早做省返工」升级成
**「不做就有一处已提交的代码是错的」**。

---

## 7. 每轮 token 用量统计（同批要做的另一块）✅ 已完工（2026-07-31）

方案 2026-07-30 定稿，2026-07-31 落地。**跟这一刀是两件事，但共用同一条 usage 链路**。

落地清单（与下文方案的出入都已就地标注）：

| 环节 | 落点 |
|---|---|
| 放闸 | `adapter._on_chat_model_end` 删掉泳道 return，主 / 子道都发 |
| 分账 | `collector._absorb_usage` 拆成分流器 + `_accumulate_usage` / `_track_context_size` |
| 出桶 | `MessageCollector.prompt_tokens / completion_tokens / usage_rows / usage_summary` |
| 落库 | `Message.prompt_tokens / completion_tokens / token_usage`，迁移 `0024` |
| 发前端 | `run_chat_stream(usage=...)` 回调 → `message_stop` 帧捎汇总 |
| 展示 | `TokenUsageBadge` + `MessageActions` 的 `extra` 插槽 |

单测 `tests/test_usage_accounting.py`（14 条），含并发同名成员分行、子道不污染层 B 判据、
终止帧延迟求值（`lambda` 被去掉就红）。

### 7.1 现状：链路通了一半

`d2ce1e4` / `8d8135b` / `b979db1` 三个 commit 已经把 usage 从模型接到了 DB（见 §4.2 表）。
**但那条链路是给层 B 判据用的**：只取主道、只要最后一次、覆盖写。
本块要的是**全部调用的累加**，是另一个用途。

> ⚠️ 别把它改坏：`tests/test_usage_accounting.py` 锁着现有行为（当时 6 条，现 14 条）。

**口径查证（2026-07-31，实读源码）**：「同一段历史被重发几次就算几次」是业界统一口径，
不是我们的发明 —— dify 的 agent 循环 `llm_usage.prompt_tokens += usage.prompt_tokens`
（`core/agent/fc_agent_runner.py`）直接累加不去重；letta 的 `LettaUsageStatistics` 是
「一次 agent 交互」的跨步汇总（带 `step_count`）。**因此这个数不等于「上下文有多长」**，
后者是 `Conversation.context_tokens` 那笔账 —— OpenHands 索性把两者存成不同字段
（`accumulated_token_usage.prompt_tokens` vs `.context_window`）。

缓存命中**不单列也不展示**：`input_tokens` 本就含缓存部分（`langchain_core` 明文规定
「Sum of all input token types」），`input_token_details.cache_read` 只是子集；
dify / letta / OpenHands 的对话界面一个都没展示它。

### 7.2 前置：放开子道闸门

`adapter.py` 的 `_on_chat_model_end` 现在有：

```python
if lane.key != LANE_MAIN:
    return          # 子 agent 的 usage 根本不发
```

统计总消耗必须放开它（成员也在烧钱）。放开后下游要能分主道 / 子道 —— **现成机制，
不用新增字段**：`adapt_chat_stream`（约 489 行）会给子道事件自动盖 `delegate_id` 戳
（`state.lane_to_delegate`），主道事件没有这个字段，有没有它就是判据。

`collector._absorb_usage` 的覆盖写逻辑**不能动**（层 B 靠它），另开一条累加路径。

### 7.3 数据落点

`Message` 加列（`models/workspace/message_model.py`）：

- `prompt_tokens` / `completion_tokens`：`IntField(db_default=0)`。
  **往有存量数据的表加非空列必须用 `db_default` 而非 `default`**，否则 NotNullViolation
- 每次派活的明细：`token_usage` JSONField，一行 = 一个调用单元，形态跟 §7.4 的展示对齐。
  **JSONB 同样要 `db_default`**（写 `db_default=[]`，Tortoise 渲染成 `DEFAULT '[]'`）——
  它和整数列一样是 NOT NULL，存量行照样会炸

两个整数列是 `token_usage` 的汇总，**刻意冗余**：整数列给 SQL 聚合（某工作区某月烧了多少），
JSONB 给界面展开。dify 的 `workflow_run.total_tokens` 同样是存下来的列而非查时算。

明细行**只存 `delegate_id` + 两个数**，不存成员名 / 任务描述 —— 那两样前端拿
`delegate_id` 去 `content` 里那个 task 块自取（`DelegateBlock.callId` 就是它），
同一份数据不存两遍。

迁移**必须 CLI 生成**，禁止手写：`uv run tortoise makemigrations -n add_message_token_usage`。
实际落地为 `0024_add_message_token_usage`，238 行存量数据全部拿到默认值、无 NULL。

### 7.4 前端展示（形态已定）

位置：assistant 消息下方的 operation 行（`MessageActions`，见 `components/chat/MessageList.tsx`）
显示本轮合计，hover 弹 popover 出明细：

```
本轮合计                      21,845
─────────────────────────────────
supervisor                    12,345
我的通用 Loop   画个SVG…        3,200
我的通用 Loop   补一个完整的…    2,800
我的通用 Loop   手搓一个…        3,500
```

三条定稿规则：

1. **成员按「派活次数」分行，同名不合并** —— 同一成员被派两次是两件不同的事
   （description 不同），合并后看不出哪次贵，定位能力就没了。而且分行是天然形态
   （`delegate_id` 本来就按派活分组），**合并反而要额外写聚合**
2. **supervisor 单独一行，其多次调用合并** —— 它没有「派活」这种天然分界
3. **最小粒度是子 agent，不统计到工具级**

任务描述取 `tool_use`（name=`task`）块的 `input.description`，取值路径参考已有的
`DelegateBlock`。

> ~~supervisor 那一行多半是大头~~ —— **实测推翻（2026-07-31）**。真实数据：
> 一轮画 SVG 的对话里 supervisor 9,336 / 成员 140,392，成员是它的 15 倍。
>
> 原因是**这两个数受不同因素驱动**：supervisor 大小看**会话有多长**（历史每轮重喂），
> 成员大小看**这次活有多重**（skill 循环里每轮重读技能提示词 + 全部工具结果）。
> 短对话 + 重活成员 → 成员碾压；长对话 + 轻活成员 → supervisor 碾压。
>
> 「量化历史膨胀」这个叙事仍然成立，但**要在同一会话里连发数轮才看得出来**
> ——盯 supervisor 那一行逐轮变大，那才是层 B 要解决的东西。

### 7.5 怎么送到前端（实施时补的决策）

**后端算好、终止帧捎一份；前端不自己累加。**

查证：dify 把累加好的 usage 塞进 `message_end` 终止帧
（`easy_ui_based_generate_task_pipeline.py`：`extras = {"usage": ...usage.model_dump()}`）；
letta 把 `usage_statistics` 作为一种流消息类型在末尾发。二者都是后端汇总、前端只显示。

> 「客户端累加」也真实存在，但那是客户端**自己就是 agent 驱动方**的场合。
> 我们的驱动方在后端，让浏览器把每帧再加一遍等于同一逻辑写两遍、还会算出两个数。

落地：`run_chat_stream` 新增 `usage: UsageSummarizer | None` 回调，
`message_stop` 帧合并 `collector.usage_summary`（三个键 = messages 表三列）。
**传的必须是 `lambda`（延迟求值）**：调 `run_chat_stream` 那一刻桶还是空的。
汇总调用单独包 try —— 它炸了不许连累 `message_stop`，前端靠那帧关活气泡。

刷新回放走 `MessageOut.token_usage`，与 SSE 那份同源（都出自 `usage_summary`），
形态跟 `artifacts` 字段的「实时走帧、刷新走 DB」完全一致。

---

## 8. 施工顺序（下一个会话）

三块活，依赖关系如下：

```
① 回放协议这一刀（§5.1 三件套）
      ↓ 做完，层 B 判据（取最后一次）才成立
② 层 B 切片 3-5：压缩 service → 接线拼装 → 测试测量

③ 每轮 token 用量统计（§7）✅ 2026-07-31 完工
```

**① 必须排在 ② 前面**：切片 3 的压缩 service 要读「哪些消息该被封存」，而回放协议
决定了这些消息渲染成什么样。协议先定，service 才不会写完推翻。

**③ 已完工**（它改了 `adapter._on_chat_model_end` 放开子道闸门 + `collector` 分流，
与 ①② 都不冲突）。它顺带给 ② 备好了度量手段：连发数轮盯 supervisor 那一行，
就能看见历史膨胀、也能事后验证压缩到底省了多少。

### 未决事项

- §5.1 的 offload 阈值取多少（deepagents 20,000 token 是单 run 内尺度，跨轮该多少要量）
- §4.4 的视角化分叉：中断态 `tool_use` 没有配对 `tool_result`，塞进结构化消息 API 会报错，
  得专门处理 —— 这是压平方案当初白捡的便宜，改回去要自己付
- 层 B 切片 4 的压缩阈值（注意 §4.2 那个 5534 的地板）
