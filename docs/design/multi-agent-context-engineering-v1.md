# 多 Agent 上下文工程 设计与调研 (v1)

> 范围：Workspace 多 Agent 的上下文工程——四件套 **Compress / Select / Write / Isolate**。Isolate 已在 V1 完成（视角化 + subagent 隔离），本文聚焦补齐 Compress / Select / Write。
> 定位：**V2 P0「多 Agent 上下文工程」**（简历核心），承接 Workspace d-1~d-3。
> 不含：RAG 进阶（另线）、RAG 性能基准（已搁置的支线，见 `knowledge-rag-benchmark-v1.md`）。

---

## 1. 目标与范围

四件套现状盘点：

| 块 | 状态 | 现状 |
|---|---|---|
| **Isolate 隔离** | ✅ 已做 | `ViewContextAssembler` 视角化 + `SubAgentMiddleware` 子 agent 隔离 |
| **Compress 压缩** | ✅ 2026-08-01 | 两层都完工：一次回复内挂框架的 `SummarizationMiddleware`；跨回复自己写（`history_budget.py` + `compaction_service.py`），实测 `10,542 → 5,022` |
| **Select 选择** | ❌ 2026-07-31 否决 | 与 Compress 的前提冲突：按 query 挑 → 前缀每轮都变 → prompt cache 全丢，等于把压缩省下的吐回去 |
| **Write 共享记忆** | ✅ 2026-07-31 划掉 | 原始诉求被沙箱产物系统覆盖：`sandbox_artifacts` 表 + `fetch_artifact` 按需取回 + 跨对话面板，形态是文件不是内存 |

**本期结果（2026-08-01）**：只做了 **Compress**，另外两块在做的过程中各自消解掉了 —— Write 的诉求被沙箱产物系统覆盖、Select 与 Compress 护 prompt cache 的前提直接冲突。**四件套至此收口。**

---

## 2. 关键决策摘要

| 决策点 | 结论 |
|---|---|
| 主线归位 | RAG 性能基准搁置（为耗 MiMo token 的支线、token 没了），回 V2 P0 上下文工程 |
| 调研方式 | 外部 agent 找方向 + 给证据 → 本地 agent 拉真源码核实 → 把关（**issue 号/行号/版本号当线索不当事实**） |
| 参考项目 | Deep Agents（同栈，主腿）/ OpenHands condenser（压缩工程标杆）/ Letta（共享记忆 + git worktree 并发标杆）；**Dify 出局** |
| deepagents 边界 | Compress 白送 · Write 半成品 · Select 零 · Isolate 已对；middleware 全可单独摘挂 `create_agent`；0.6.10 够用不必升 |
| Compress 形态 | **两层**：单 run 内挂 `SummarizationMiddleware`（白送）+ 跨轮历史在 `ViewContextAssembler` 层自己压（deepagents 帮不上） |

---

## 3. 调研结论

### 3.1 排除：Dify
单次 agent run 内 scratchpad（`_current_thoughts` / `_agent_scratchpad`）只增不减（init / append / 全量喂），唯一保护是 `max_iteration` 硬刹车，**无压缩 / 裁剪 / 记忆**。跨会话有 `TokenBufferMemory` 做 token 裁剪，但 run 内不管。→ 不对口，出局。

### 3.2 对口标杆（本地深挖用）
- **Deep Agents**（`langchain-ai/deepagents`）：与 LangGraph 同栈，middleware 式上下文管理。**主腿，直接抄作业启用**。
- **OpenHands**（`All-Hands-AI/OpenHands`）：Condenser 体系（LLMSummarizing / AmortizedForgetting / BrowserOutput），压缩工程最成熟。学思想。
- **Letta**（`letta-ai/letta`）：MemGPT 分层记忆 + **Context Repositories（git-backed memory，subagent 独立 worktree 并发写 + git merge 解冲突）**。**多 agent 共享白板（Write）的标杆**。
> 纪律：上述调研里的具体 issue 号 / 行号 / 版本号当线索、不当事实，本地真源码兜底。

### 3.3 deepagents 0.6.10 能力边界（本地源码核实）

| 块 | deepagents 给多少 | 你还得自己干 |
|---|---|---|
| **Compress** | ✅ **白送** `SummarizationMiddleware`（浅包 langchain 核心 + 旧消息 offload 到 `conversation_history/{thread_id}.md`）；可单独 `new` + 挂 `create_agent` | 几乎不写 |
| **Write** | 🟡 给 backend 载体（State / Filesystem / Store / Composite）+ `MemoryMiddleware` 注入 `AGENTS.md`；**无共享白板成品**（靠 agent 自己 `edit_file` 改文件） | 共享语义自己用同一 backend 搭 |
| **Select** | ❌ **零**（grep 全无 relevance / retrieval / embedding / similarity） | 自己做 RAG over history |
| **Isolate** | ✅ `SubAgentMiddleware`（`_EXCLUDED_STATE_KEYS` 隔离，子 agent 只收一条 `HumanMessage(description)`） | 已对 |

- 所有 middleware 都是 langchain `AgentMiddleware` 子类，**可单独摘出来挂普通 `create_agent`**，不绑 `create_deep_agent`。
- 0.6.10 已含 Compress + Eviction + Offload；新版（0.6.12）无新上下文能力，**不必升**。

---

## 4. Compress 落地方向（两层）

**关键接缝**：workspace 跨轮历史在 **DB 全量重放、没挂 checkpointer**（`ViewContextAssembler` 每轮拉 `past` 全量 build）。所以 Compress 在本项目是两层，别以为挂个 middleware 就完事：

- **层 A（单 run 内）**：挂 `SummarizationMiddleware` 到 supervisor + 各成员的 `create_agent` → 压**一次 run 内**派活 / 工具调用堆积的上下文。**deepagents 白送**。
- **层 B（跨轮历史）**：在 `ViewContextAssembler` 层自己做——摘要旧轮存 DB + 留近 N 轮（roadmap 说的"长对话历史压缩"主体）。**deepagents 帮不上**。**✅ 2026-08-01 完工**，阈值 / 摘要形态 / 失败三层 / 实测数字见 `docs/context.md` 最近迭代。

> 方案细节（触发阈值、摘要存哪张表、怎么跟视角化协议 `<msg from>` 配合、跟 prompt cache 的关系）**已在 2026-08-01 那一轮逐条讨论并落地**，结论记在 `docs/context.md` 最近迭代，不在本文重复。

---

## 5. 留口子（Write / Select）

- **Write**：用 backend 当载体搭"workspace 级共享白板"；参考 **Letta 的 git worktree 并发 + 冲突解决**思路解决"多成员同时写不打架"。
- **Select**：对历史消息做相关性检索（RAG over messages）；deepagents 无、自研。

---

## 6. 下一步

**本文已完结。** 四件套收口于 2026-08-01（Compress 两层完工、Select 否决、Write 划掉、Isolate 早已完成）。后续如果重新捡起 Select / Write，要先推翻上表里记的那两条否决理由。
