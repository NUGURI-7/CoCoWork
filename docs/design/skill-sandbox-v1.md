# P5 · Skill 执行 + 沙箱 — 设计决策（v1，2026-07-24 冻结）

> 本文件是 P5 的**决策记录**，不是实现方案。每条决策附依据（源码路径或推导过程），
> 便于日后复核；没有依据的条目显式标注为「产品决策」或「估算，待实测替换」。
> 实现方案另出。
>
> **2026-07-26 修订 ①**（片 2a 落地过程中，实测推翻的部分）：决策 **3 / 6 / 7** 关于内置 skill
> 的形态整体改判（内置不入表、不可删改、按 name 挂载）；决策 **9a** 关于 zip bomb 的判断修正；
> **C.1** 补「路径由 driver 决定，本地与容器路径字面不可能相同」。改判处一律保留原文与推翻理由，
> 不要照着记忆里的旧版本做。落地清单见 §5.5。
>
> **2026-07-26 修订 ②**（产物回传设计期，需求澄清后推翻的部分）：**只有交付区的产物会被持久化**，
> 工作区不再整体同步。连带改判 **决策 14**（持久化对象从「整个工作区」缩小为「产物」）、
> **C.1**（加第四个挂载点：交付区）、**C.2**（快照比对整段作废）、**§5.5**（ArtifactMiddleware 推翻）。
> **推翻的根因记在 C.2 末尾，是本片最值得复用的一条**：两个不同的需求被一套机制同时回答了。
>
> **2026-07-27 修订 ③**（LocalDocker 落地前的方案讨论，用户拍板三条）：
> ① **LocalShell 不是脚手架，是发布的一个 driver** —— 面向 clone 项目的开发者（不装 docker 也能跑通
> 整条 skill 链路），生产部署走 docker。连带 **决策 18** 补一档、**§5.5 片 2a** 的「脚手架」措辞作废。
> ② **docker daemon 可以是远程的**（`DOCKER_HOST=ssh://`），开发机不必装 Docker Desktop。
> 连带 **§3** 补开发形态。这条能成立的**前提**正是不用 bind mount，见新增的 **C.3**。
> ③ **`/workspace` 不再铺入全部历史产物**：本对话的自动铺、跨对话的给模型一个工具按需取。
> 连带改判 **决策 14**（新增 14a）与 **C.1**。改判处一律保留原文与理由。
>
> **2026-07-29 修订 ④**（14a 落地前的讨论，**整条推翻重来**）：**`/workspace` 每轮都是空的，
> 什么都不自动铺** —— 本对话的产物只把**清单**渲染进历史消息，实体由模型调工具按需取；
> 跨对话的连清单都不给模型，由用户在前端把产物**拖进输入框**带进来。连带 **决策 14a** 整条作废重写、
> **C.1** 与 **C.3** 各改一行、新增 **决策 24 / 25 / 26**。
> **本轮最值得复用的一条：切分线是「引用 vs 实体」，不是「本对话 vs 跨对话」。**
> 换了这条线之后，原方案里「铺几条」「什么算本对话」「同名取哪个」那一串没有正确答案的问题
> 一起消失了 —— 见 14a 的推翻理由。

---

## 0. 定位

做 Skill 的**执行能力**：一个带脚本的 Skill 能被 agent 调用、在容器内执行、产物回传，宿主机无副作用。

**一句话架构**：agent 循环留在应用进程，沙箱是一次性 Docker 容器；一次完整回复借还一个容器，
容器内所有命令走 `docker exec` 靠文件传递产物，回复结束把**交付区**的产物收进对象存储、销毁容器。
产物绑 **workspace**（跨对话可见），不绑容器、不绑对话；**中间文件一律不持久化**。

---

## 1. 调研基线（五家横向）

本片所有决策来自对本地仓库源码的实读，不引用二手结论。

### 1.1 Skill 机制 —— 四种做法，**没有一家把 skill 做成函数签名**

| 项目 | Skill 存在形式 | 正文如何送达模型 |
|---|---|---|
| **deepagents** 0.6.10 | backend 上的目录（`middleware/skills.py`） | 提示词给**路径**，模型用 `read_file` 自取 |
| **OpenHands** | agent-server 返回的 `Skill` 对象 | 命中 trigger 时**正文直接注入**（`KeywordTrigger` / `TaskTrigger`） |
| **Dify**（dify-agent `dify.drive` 层） | drive 条目，**只声明 metadata 不带 content** | 提示词给一条 **shell 命令** 让模型自己 pull |
| **Letta** | memory block：`skills/{name}/SKILL.md` → block label（`memory_repo/path_mapping.py`） | 不用读，block 本来就常驻 |
| **RAGFlow / LlamaIndex** | 无 skill 概念，只有代码执行沙箱 | — |

### 1.2 沙箱 —— 三档形态

| 档 | 形态 | 谁在这档 |
|---|---|---|
| 1 · 代码解释器 | 只有「执行这段代码、返回输出」 | RAGFlow、Letta、LlamaIndex 托管集成 |
| **2 · 带工作区的沙箱** | 容器有工作目录：能投文件、跑命令、取产物；agent 循环仍在应用进程 | Dify（shellctl）、**本项目** |
| 3 · agent 搬进沙箱 | 应用只剩控制面，agent 循环全在容器内 | OpenHands |

**关键更正（曾归错档）**：Dify 的 agent 循环**不在**沙箱里 —— dify-agent server 是后端服务
（依赖 Redis / plugin daemon / inner API），沙箱镜像只装 `shellctl` + CLI stub。
只有 OpenHands 是档 3，而它的产品形态本身就是「卖你一台机器」。

### 1.3 执行隔离 —— 唯一的反面教材

`deepagents/backends/local_shell.py` docstring 原文：提供 **NO** sandboxing；
**不适用**生产环境 / 多租户 / 不可信输入；生产请自己继承 `BaseSandbox`。

**MaxKB 干的正是这条 docstring 禁止的事**（`apps/application/flow/tools.py:468`）：
`SandboxShellBackend` 继承 `LocalShellBackend`，与 Django 同进程跑 subprocess。
其「沙箱」是 `sandbox_shell.py` 中约 200 行手写 shell 状态机解析 + `LD_PRELOAD` + `gosu`。
三个要害：① 安全边界是一个对 LLM 生成字符串做解析的解析器；
② 默认 `SANDBOX=0`（`common/utils/tool_code.py:25`）整套关闭；
③ skill 凭据以明文 `.env` 写进 skill 目录后 `chmod -R g+rx`。

**结论：五家里唯一在进程内跑不可信代码的是 MaxKB，代价即上述三条。**

---

## 2. 决策清单

### A. Skill 是什么

| # | 决策 | 依据 |
|---|---|---|
| 1 | 形态 = 目录 + `SKILL.md`（YAML 头 name/description + 正文 + 捆绑脚本），对齐 agentskills 标准 | deepagents 完整实现该规范；OpenHands 有 `is_agentskills_format` 位；Dify 存 `<slug>/SKILL.md`；Letta 映射 `skills/{name}/SKILL.md` — **四家源码互证** |
| 2 | Skill 与 tool **同级资源**（可挂载、可管理、UI 平起平坐），但运行时**不是函数签名** | MaxKB `ToolType.SKILL` 与 INTERNAL/CUSTOM/MCP 并列（建模层）；五家运行机制均为「文本进上下文 + 通用工具执行」（运行时层） |
| 3 | 两个来源：**内置**（随代码分发，`backend/app/skills/builtin/<name>/`）+ **用户上传**。**内置不进 `skills` 表** —— 本体在代码里，启动时扫盘进内存注册表（`app/services/skill/builtin.py`）；表里只可能有一种内置行：用户给某个内置 skill **配了 key** 时产生的凭据行，没配 key 则零行 | **2026-07-26 推翻原决策**（原文：「两者共用同一条入库路径，内置只是 seed 进表的种子数据」）。改判依据 = **Dify `tool_builtin_providers` 表**：字段只有 `tenant_id / user_id / provider(字符串) / encrypted_credentials`，**没有 description、没有工具定义**，即内置工具本体在代码里，DB 只存「某租户给某内置 provider 配的凭据」，没配凭据就一行都没有。原决策的理由「共享行挂不上 per-user 凭据」正是被这个形态解掉的。收益：消掉 N×M 行、消掉 seed 遍历用户、内置包升级改代码即可零数据动作。放 `app/` 下仍是硬约束 —— `pyproject.toml:66` 是 `packages = ["app"]`，放外面构建镜像时带不进去 |

### B. Skill 怎么存

| # | 决策 | 依据 |
|---|---|---|
| 4 | 用户上传的：**DB 存元数据 + 对象存储存 zip 本体**，复用现有 `storage` 抽象（R2/Local）。表里只放 key，不存字节 | Dify `agent_drive_files` 表是路径 KV、**从不存字节**；MaxKB File 表存 zip；Letta block 表 — 三家一致。本项目 Document 表已是此形态 |
| 5 | **独立 `skills` 表**，不塞进 tool 表 | 反面教材 = MaxKB `tool` 表的 `code` 字段：CUSTOM 存 Python / SKILL 存 File id / MCP 存别的，一字段三语义、大量列对某类型恒空。正面 = 本项目 `MCPServer` 已独立成表 |
| 6 | **内置 skill 不可删、不可改，用户唯一能动的是 key。** 「我不想要」= 从 `AgentConfig.builtin_skills` 里去掉那个 name（挂载层的事，跟 skill 行无关），与停用内置工具同构 | **2026-07-26 推翻原决策**（原文：「不是权限位，两者都可删改」）。原理由「随决策 3 改成 per-user 行后失去意义」站不住 —— **per-user 的行照样可以是只读的**。硬证据两条：① **Letta** 的 `read_only` 位在 `core_tool_executor.py` 被检查 **8 次**（320/336/354/530/665/691/744/899），每个写入口都查；② **Dify** 的 `delete_builtin_tool_provider(tenant_id, provider, credential_id)` 删的是**凭据**不是工具 —— 内置工具本体删不掉。连带收益：不可删 = 没有「被删掉」这个状态，注册表每次启动重扫不会复活任何东西 |
| 7 | **两个字段，两种标识**：`skills: list[UUID]`（用户上传的，DB 实体）+ `builtin_skills: list[str]`（内置的，按 name） | **2026-07-26 修订**（原文：「保持 UUID 不变」）。随决策 3 而变 —— 内置的凭据行**可能不存在**（没配 key 时零行），UUID 引用不了一个还没出生的东西；而挂载与否必须跟「有没有行」完全无关。**这不是新发明**：项目里 `builtin_tools: list[str]`（按 name）与 `mcp_servers: list[UUID]`（按 id）本就并存，内置 skill 天然属于前者 |
| 8 | 写入口**收在 service 层**；沙箱与 agent 永不持有 DB 凭据 | Letta `core_memory_append` 走 manager + `actor` + `read_only` 校验；Dify agent stub 用 JWE 令牌回调应用；OpenHands session key 仅 RUNNING 时有效 — 三家一致 |
| 9 | 流通性 = **上传入库 ✅ / 导出 ✅**；外部源导入、市场 **留字段不实现** | 导出 = 拉归档，零成本（原「不做」已收回）。Letta `SkillSchema.source_url`、OpenHands `MarketplaceRegistration` 证明分发是数据模型的一部分，故留字段 |
| 9a | 上传侧校验：**zip 大小上限** + **必须含 `SKILL.md`** + **frontmatter 合规**（见下）+ **成员路径不含 `..` / 不以 `/` 开头** | 末项抄 MaxKB `flow/tools.py:412`（`if ".." in member or member.startswith("/"): raise`，这段它做对了）。**其价值是「早报错 + 不依赖工具默认行为」，不是「不做会被黑」** —— 2026-07-25 实测：Python `zipfile.extractall` 已自动剥掉 `..` 与前导 `/`（CPython 文档明载），恶意条目落在目标目录内而非穿出去。但默认行为是**静默剥离**（用户不知道包有问题），且我们在容器内用 `unzip` 解压（决策 21a）时保护取决于那个 `unzip` 的版本与参数，已不在 Python 的保护范围。**~~大小上限挡不住 zip bomb~~ —— 2026-07-26 修正：这句不完整。** zip 的中央目录里逐条记着**解压后大小**（`ZipInfo.file_size`），把它们求和就能在**解压之前**拦下 zip bomb，成本近乎为零。**Dify 就是这么做的**（`api/services/agent/skill_package_service.py`）：`_MAX_ARCHIVE_BYTES 50MB` + `_MAX_UNCOMPRESSED_BYTES 200MB` + `_MAX_ENTRIES 5000` + `_MAX_SKILL_MD_BYTES 1MB` 四道，外加扩展名白名单与 `unsafe_path`。故 zip 层把关照抄 Dify 这一套（**必须自己写，`skills-ref` 完全不管这层**）；容器的 `--memory` + tmpfs size 退为最后兜底而非唯一防线。**注意声明值可以撒谎**，读单个成员时仍要用「流式读 上限+1 字节」而不是信 `file_size` |
| 9b | frontmatter 校验按 **Agent Skills 规范原文**（https://agentskills.io/specification ，2026-07-25 已核对原文，非转述）：`name` 必填、1-64 字符、仅小写字母数字与连字符、不以 `-` 起止、无连续 `--`、**须等于父目录名**；`description` 必填、1-1024 字符；`license` / `compatibility`(≤500) / `metadata` / `allowed-tools` 可选 | 校验动机是四件具体事，不是「为了合规」：① 缺 `name`/`description` 则 prompt 片段拼不出来；② `name` 会进 prompt 且被当目录名，含空白或 `/` 会出诡异问题；③ 长度上限防单个描述把 prompt 撑爆；④ 对齐规范意味着聚合站下载的包能直接用（官方另有 `skills-ref validate` 工具）。**「须等于父目录名」并非我们的正确性必需**（deepagents 单独存 `path`、我们单独存 `storage_key`，都不靠 name 找文件），仍硬校验只为对齐规范 —— 曾以「否则找不到文件」为理由，该理由已收回 |
| 9c | **prompt 膨胀不是问题，v1 全部常驻**；真挂多了再上 trigger | 规范「渐进披露」节自述：metadata（`name`+`description`）**约 100 tokens/skill**，启动时全部加载；1024 是硬上限非目标（Anthropic pdf skill 描述约 250 字符）。且挂载是用户显式选的（`AgentConfig.skills`），非全库注入 —— 与「挂 5 个工具就常驻 5 份 schema」同量级，工具 schema 通常更长。将来若需按需注入，照 OpenHands 的 `KeywordTrigger` / `TaskTrigger`（用户消息命中关键词才注入），决策 22 自拼 prompt 的形态天然容得下 |

**表结构**（迁移 0017 已落地，字段不变；**语义随决策 3/6 改了**）：
```
skills
├── created_by            FK User
├── name                  SKILL.md 的 name（LLM 可见标识）
├── description           SKILL.md 的 description（进 prompt 供判断）
├── source_type           builtin | user   ← 来源溯源（非权限位）
├── storage_key           对象存储 zip 的键
├── credentials_encrypted 运行所需环境变量 dict（整体 JSON Fernet 加密）
├── skill_metadata        jsonb：原包文件清单等（抄 Dify `skill_metadata`）
├── enabled
└── 时间戳
```

**表里有两种行，别混**：

| | `source_type=user`（上传的） | `source_type=builtin`（内置的） |
|---|---|---|
| 这行是什么 | **skill 本体的索引** | **仅仅是一份 key**，本体在 `app/skills/builtin/<name>/` |
| 何时产生 | 上传时 | **用户填 key 那一刻**；不需要 key 的内置 skill 永远零行 |
| `storage_key` | 对象存储的键 | 恒空（没有 zip） |
| `description` 等展示字段 | 有效 | **不作数**，一律以代码里的 `SKILL.md` 为准（存冗余副本会跟代码漂移） |
| 可删改 | 可 | **不可**，只能改 key |

> 有人会拿决策 5 批评 MaxKB 的那句「大量列对某类型恒空」来反对这个设计。**不适用**：MaxKB 的病是 `code` **一列三语义**（读之前得先判类型才知道这列装的是什么），而这里没有任何一列语义会变 —— `storage_key` 永远是「zip 在对象存储的键」，内置行只是没有 zip 所以为空。**空值不是多义。**

**「需不需要 key」写在 `SKILL.md` 的 `metadata` 里**，规范对该字段的定义原文即 "Key-value pairs for **client-specific properties**"：

```yaml
metadata:
  required-env: OPENWEATHER_API_KEY OPENWEATHER_UNITS   # 空格分隔，形态对齐 allowed-tools
```

它是**给前端的预填提示**（该摆几个 key 输入框、分别叫什么），**不是白名单** —— key 编辑器允许用户自己加行（同 `MCPServer.headers`，决策 15 已定 UI 同构）。故从聚合站下来的包没写这个字段也能配 key，不用改包重打。**一条约定同时覆盖内置与上传两种来源。**

### C. 沙箱怎么跑

| # | 决策 | 依据 |
|---|---|---|
| 10 | 执行**跨进程边界**、Docker 容器隔离；web 进程不碰 docker | §1.3；且与 P2 既定「docker SDK 绝不能进 web 进程」同一条边界 |
| 11 | **一次性容器**：起 → 跑 → `docker rm`。不用 restart 复用（省的几秒不值），池化推后 | 销毁式清理使「清理漏网 = 跨用户数据泄露」这类 bug 不存在。RAGFlow 池化可行的前提是 read-only + tmpfs（清理近乎免费），与本项目取舍不同 |
| 12 | **借还粒度 = 一次完整回复**（一条用户消息 → agent 与 LLM 转 N 圈 → 吐完回复）。轮内所有命令打进**同一容器** | 若按单条命令借还，一轮十几步就要解包/打包十几次，方案作废 |
| 13 | 命令执行 = **`docker exec`**，不上容器内守护进程 | 守护进程唯一多买到的是 shell 会话态（cwd 延续 / 后台常驻），Dify 需要（tmux 长会话）、OpenHands 需要（`npm run dev` 后测网页）；本项目 skill 是跑完即止的脚本，用不上。**产物跨命令传递靠文件、与此选择无关**（文件在容器磁盘，活得比 shell 进程久） |
| 14 | **持久化的是产物，不是工作区**（绑 workspace，不绑容器、不绑对话）：产物活在对象存储，容器与工作区随时可销毁 | **2026-07-26 修订 ②**（原文：「**工作区状态**绑 workspace……状态活在对象存储」）。**改的是持久化的对象，不是绑定粒度** —— 绑 workspace 这条不变（Letta 绑 agent、Dify 绑 `agent-<agent_id>`，本项目 workspace 才是那个持久实体：自带 supervisor + 招募成员 + 跨多个 conversation）。改的是「留什么」：中间文件任何情况都不留，只有**被显式交付到交付区的成果**才活得过这一轮（产品决策，2026-07-26 用户拍板）。**连带效果**：跨对话可见的东西 = 历史**产物**（~~容器启动时铺回工作区~~，铺回策略见 14a），不再是 agent 的全部工作痕迹；OpenHands `sandbox/workspace_archive.py` 那套「整个工作区打包传对象存储」**不再适用**，它服务的是 coding agent（工作区就是 repo、每个文件都是成果），与本项目形态不同 |
| 14a | **`/workspace` 每轮都是空的，什么都不自动铺。** 本对话的产物只把**清单**渲染进历史消息（决策 24），实体由模型调 `fetch` 工具按需取回；跨对话的连清单都不给模型，由用户在前端**拖引用**带进来（决策 25）。两个 driver 一致 —— local 的 `/workspace` 也改成每轮清空 | **2026-07-29 修订 ④ 整条推翻**（原文：「铺回分两档：本对话的产物容器启动时自动铺进 `/workspace`；跨对话的不铺，给模型一个取回工具按需拉」）。**原方案错在切分线选错了**：它按「本对话 / 跨对话」切，于是「什么算本对话」「铺几条」「同名取哪个」「Playground 没有对话实体怎么办」全都要现编答案，而这些问题**没有一个有正确答案**。正确的切分线是**「引用 vs 实体」** —— 清单是一行文本（几十 token），实体是一次对象存储往返加几十 KB 到几十 MB，**贵的从来只是后者**。分开之后每轮固定开销 = 一次 DB 查询，**与这个 workspace 攒了 3 个还是 300 个产物无关**；原方案想靠「只铺本对话」压住的那个线性增长，压根就不存在了。**连带收益**：两档变一档（一套机制而非两套），「什么算本对话」这个在 Playground 那边本来就说不清的问题直接消失（决策 26）。**代价照实记**：上一轮刚产出的图这一轮要改，得多调一次 `fetch`（约 1 秒）—— 原方案里这种情况是自动就位的。换来的是每轮不再无条件拉几个文件 + 少维护一套机制，这笔换划算。**local driver 跟着改成每轮清空**：不改的话开发时文件永远「自己就在」、`fetch` 一次都不会被触发，等部署到 docker 才发现模型不会用它 —— **开发环境把 bug 藏起来了**。清空是安全的：`collect_artifacts` 对两个 driver 一视同仁，产物早已进了对象存储。<br><br>**以下为原 14a 的推翻理由，其判断仍然成立，保留**（2026-07-27 修订 ③，当时推翻的是「容器启动时铺入历史产物」即全量铺）。**为什么原方案不成立**：本地 driver 时 `/workspace` 是宿主机目录、天然一直在，「铺回」是免费的；换容器后每轮都是全新空容器，铺回变成**每轮按产物条数拉一遍对象存储**，开销随历史线性增长，而绝大多数轮次一个历史文件都用不上。**为什么切在「本对话」这条线上**：「刚才那张图再改改」是高频且模型不该为它多绕一次工具调用，而它的量级恒定在几个；真正会膨胀的是跨对话那部分（一个 workspace 攒几十上百个产物），恰好也是低频。**代价照实记**：跨对话那档押在「模型看得到清单且想得起来取」上，会漏 —— 但漏的后果是「没用上旧文件」，不是「产物丢了」，与 notes §9 里 `publish_artifact` 那条软肋不同量级 |
| 15 | 带 key 的 skill：**Fernet 加密存 DB → 运行时解密 → `docker run -e` 启动注入** | 同本项目 Provider API key、MCPServer headers 既有做法。注入时机是「起容器时」，故与命令怎么跑无关 |
| 16 | 容器加固：`--read-only` + tmpfs + `--user nobody` + **`--memory 512m`（含 `--memory-swap` 同值）** + `--cpus` + **`--pids-limit` + `--cap-drop ALL` + `--security-opt no-new-privileges`**；装 Python + Node | 前五条直接抄 RAGFlow `executor_manager/core/container.py:82` 的 `create_container`。**2026-07-27 修订 ③ 改两处**：① **256m → 512m** —— 原数是按「脚本自己吃多少」估的（§5 那条实测：裸解释器 15MB、`import pandas` 73MB），**没算 tmpfs**：四个可写挂载点都是内存盘，落进去的文件占的是同一份 cgroup 额度，故上限要覆盖「脚本内存 + 文件」。同时补 `--memory-swap` 同值，否则超限会去吃 swap，`--memory` 形同虚设。② 补三条 RAGFlow 没有但属标配的：`--pids-limit`（防 fork 炸弹）、`--cap-drop ALL`（收掉全部内核特权）、`--security-opt no-new-privileges`（容器内提不了权）|
| 17 | **网络**：沙箱容器接**专用 docker network**（网络内只有沙箱自己，PG / Redis / web 都不在）→ 能出公网、连不到内部服务。**外加一条防火墙规则**拦云元数据地址：`iptables -I DOCKER-USER -d 169.254.169.254 -j DROP` | 靠网络拓扑而非 iptables 规则集，Mac / Linux 一致。**元数据地址必须单独拦** —— 它返回的是可直接调云 API 的 IAM 临时凭据，不是配置信息；Capital One 2019 即由 SSRF 打到该地址窃取凭据、泄露约 1 亿条客户数据（AWS 因此推出 IMDSv2）。**RAGFlow 的做法不可照搬**：它靠 AST 静态分析禁 `socket`/`http.client`/`os`/`subprocess` 等 import（`services/security.py`），那是纯计算节点的做法，skill 要调外部服务、禁不得 |
| 18 | **抽象层 + 多 driver**：**LocalShell（面向开发者，随项目发布，不装 docker 即可跑通）+ LocalDocker（生产）**；远程执行机 / E2B / 阿里云 FC **留实现位不做**。gVisor 是 Linux 上的启动参数，代码不动 | **2026-07-27 修订 ③**：原文只列 LocalDocker 为首发，把 LocalShell 当片 2a 的一次性脚手架。改判理由是**产品定位**（用户拍板）：clone 项目的人不该被「先装 Docker Desktop」挡在门外，本地那档跑的本来就是他自己的东西 —— 同 notes §18 记的 runify 形态（Local / Docker 两个 runner 并存，且**本地那档不冒充隔离**）。**故 LocalShell 一行不改、原样保留**，只是不再叫脚手架。多 driver 依据：RAGFlow 5 provider、Letta 3、OpenHands 3 — 四家一致。同本项目 Storage(R2/Local)、Splitter、Parser 既有姿势 |

#### C.1 容器目录布局

```
/skills               ← 挂载的 skill 解压于此（只读）
/workspace            ← 工作台：**每轮都是空的，什么都不自动铺**（决策 14a）。要用旧产物由模型 fetch 取回
/outputs/<本轮 id>/   ← 交付区：每轮新建的空目录。放进来的才是产物
/tmp                  ← 本轮草稿（tmpfs 内存盘）：销毁即弃
```

除这四处外整个文件系统 `--read-only`。**草稿区直接用 `/tmp`**（Linux 标准语义，脚本作者与 LLM 都天然知道它会被清掉，无需在 prompt 里额外解释；RAGFlow 亦挂 `--tmpfs /tmp`）—— 不自造 `/scratch` 之类的名字。

**交付区是 2026-07-26 修订 ② 新增的，它是「哪些是产物」这个问题的全部答案**（依据见 C.2 末尾）。三条硬约定：

1. **每轮一个新的空目录**（目录名 = 本轮 `message_id`）。里面有什么就是本轮产物，**不需要跟任何东西比对** —— 目录是空的开始的，没有历史可混。
2. **`execute` 的工作目录 = `/tmp`（草稿区），不是交付区。** 脚本随手写的相对路径文件（`temp.json`）落草稿区、不进卡片；成果必须由模型用 `--out` 显式写进交付区。曾想把工作目录设成交付区以兜住「脚本硬编码输出文件名」的情况，**当场推翻**：那会让所有正常 skill 的中间文件也落进交付区 —— 拿大代价换小风险。
3. **残余风险照实记**：脚本不接受输出路径参数、自己写死文件名时，成果落在草稿区、没有卡片（文件不丢）。**这一层任何系统都堵不上** —— 「哪个是成果」是语义，脚本没说出来就不存在于任何地方。正常 skill 不会这样（输出路径不可指定的脚本，agent 根本没法用）。

**上面这些路径是 docker driver 的值，不是全局常量。**（2026-07-26 落地时补）
路径由 driver 决定，代码里是 `SandboxPaths(root / skills / workspace / outputs / tmp)`，prompt 拼接时从它取值：

| driver | 模型看到的路径 |
|---|---|
| LocalShell（开发者 driver，决策 18） | `<root>/skills`、`<root>/workspace`、`<root>/outputs/<id>`、`<root>/tmp` —— 宿主机真实绝对路径 |
| LocalDocker | `/skills`、`/workspace`、`/outputs/<id>`、`/tmp` —— 容器内路径 |

**「本地与容器路径字面相同」这个目标拿不到，别再尝试。** 曾想用 `LocalShellBackend(virtual_mode=True)` 造一个假根让本地也显示 `/skills`，**实测失败**：`virtual_mode` 只映射那 7 个工具里的文件类工具，`execute` 交给 `sh -c` 执行、由操作系统按真实文件系统解析，直接报 `can't open file '/skills/svg-chart/scripts/bar.py'`。deepagents 自己的告警原话即 *"virtual_mode does not restrict shell execution"*，且其自带 prompt 明写 *"All file paths must start with a /"* —— **文件工具与 shell 必须共用同一个路径空间**，本地只能用 `virtual_mode=False` + 宿主机绝对路径。真正要保住的性质是「prompt 里的路径与实际路径一致」，那个两种 driver 下都成立；字面相同只是曾经以为能白拿的东西。

#### C.2 回收机制：只收交付区（2026-07-26 修订 ②）

**一轮结束 → `ls` 交付区 → 收进对象存储 → 落一条记录带 `message_id`。**

**object key = `sandbox/{workspace_id}/{message_id}/{文件名}`。**
```
/outputs/019e.../sales.svg  ←→  sandbox/{wsid}/019e.../sales.svg
```

带 `message_id` 是**必需**的两个理由：① 回放时按消息归组（没有它事后无法把产物挂回那条消息）；
② 两轮都产出 `chart.svg` 不会互相覆盖。

**不需要快照、不需要比对、不需要判断「哪些变了」** —— 交付区每轮是新建的空目录，
里面有什么就是这一轮交付的，数一数即可。

**安全边界**：`workspace_id` 与 `message_id` 均由服务端生成，绝不接受来自 skill / LLM 的输入；
文件名防穿越复用 Local storage 后端既有的防护。

---

**以下为原方案，已整段作废，保留以记录推翻理由：**

> 原 C.2 = **同步整个工作区，按文件、不按整包**：key = `sandbox/{workspace_id}/{相对 /workspace 的路径}`；
> 靠一份「进门快照」（`{相对路径: 内容指纹}`）在容器销毁前重算比对，新增与修改的才上传；
> 不加锁（两个对话写不同文件天然无冲突），撞同一 key 后写赢 + 记日志。
> 论证过「整包是 read-modify-write 必然丢更新，分子目录不解决」——**那段论证本身没错**，
> 只是它要解决的问题现在不存在了。

**推翻的直接原因**（产品决策，2026-07-26 用户拍板）：**中间文件任何情况都不持久化**，
只有最终产物需要留。一旦持久化对象从「整个工作区」缩小成「交付区里的成果」，
快照比对要回答的那个问题（哪些文件变了）就没有了 —— 要存的东西本来就在筐里。
连带「丢更新」也消失：key 带 `message_id`，两个对话根本写不到同一个 key 上。

**推翻的根本原因（本片最值得复用的一条）：一套机制被同时用来回答两个不同的问题。**

| | 要回答的问题 | 想要什么 | 正确的机制 |
|---|---|---|---|
| **A** | 容器要销毁了，哪些文件得留住 | 曾以为是「全部变更」 | 快照比对 |
| **B** | 哪些是给用户看的产物卡片 | **只要成果** | 交付区 |

原 §5.5 直接把 A 的机制（快照比对）拿去做 B（产物清单），于是一路在文件系统里挖
「哪个是成果」这个语义 —— **而语义不在文件系统里，怎么挖都挖不出来**。
澄清需求后 A 收缩成 B，两者合并，快照比对整个不需要了。

**可迁移的判据**：拿到一个「怎么做」时，先确认它服务的「要什么」——
尤其当那个「怎么做」是从旧文档抄来的，文档里的机制很可能是为另一个目标设计的。

#### C.3 文件怎么进出容器：不用 bind mount（2026-07-27 修订 ③ 新增）

**tar 字节经 `docker exec` 的 stdin / stdout 进出，由容器内的 `tar` 解包与打包；一处 bind mount 都不用。**
落点即决策 21 的 `upload_files()` / `download_files()`，`BaseSandbox` 的抽象面本来就长这样。

| 时机 | 动作 |
|---|---|
| 容器起来后 | skill 目录在 web 进程内打成 tar → 灌进 `exec("tar -x -C /skills")` 的 stdin（决策 21a） |
| 模型 fetch 旧产物时 | 从对象存储取字节 → 同法送进 `/workspace`（决策 14a / 24） |
| 一轮结束 | `exec("tar -c -C /outputs <mid>")` 收 stdout → 进对象存储（C.2） |

> **~~原文：全部走 docker API 的 `put_archive` / `get_archive`（即 `docker cp` 的程序形态）~~
> —— 2026-07-28 实测推翻。** `docker cp` 那套接口读写的是**容器的可写层**，够不着 tmpfs 挂载：
> 实测同一个容器里 `put_archive` 报 500、`get_archive` 报 404，而容器内 `ls` 明明看得见文件
> （tmpfs 归内核管，不归 docker 的存储驱动管；docker 文档亦列明 `/proc`、`/sys`、tmpfs、
> 用户挂载都拷不了）。**病根不是这条决策本身错，是它与决策 16（四个可写目录全 tmpfs）
> 各自成立、交集为空 —— 而两条决策没被放在一起验过。**
> 换 exec + tar 后加固参数一条不用让步，反而更快（实测 51KB 上传 / 下载各 0.55s）。
> 顺带对齐了真实产品：RAGFlow / Dify 都不用 docker cp，文件走容器内的进程收发；
> deepagents 自带 backend 亦然（它用 base64 塞命令行，我们直接灌裸字节，省掉 33% 膨胀，
> 也不受 argv 单参数 128KB 上限）。
> **另一个选项是把四个目录换成 docker volume（cp 接口对 volume 实测可用），已否决** ——
> 那要拿内存盘语义、tmpfs 的 size 上限（zip bomb 的最后一道闸）和「容器一停即消失」去换
> 「代码不用改」。

**为什么这条路上的关键实现细节要记下来**（都是不实测发现不了的）：

- **上传靠关闭 socket 写端**（`shutdown(SHUT_WR)`）告诉容器内的 `tar` 数据到齐了，不关它会一直等。
- **下载必须 `stderr=False`**：docker 会把 stdout 与 stderr 合进同一个流，`tar` 一旦有警告文本，
  包就废了。而给模型跑命令的 `exec` 恰恰相反，要合并（那才是「终端里看到的样子」）。
- **`use_ssh_client=True` 不能开**（仅影响远程 daemon 的开发形态，见 §3）。

**为什么不用 bind mount（按强度）**：

1. **bind 的路径是「docker daemon 那台机器」上的路径，不是调用方的。** 一旦 daemon 不在本机
   （远程 daemon、或 sandboxd 自己在容器里跑 = §3 的 DooD 形态），宿主机 `data/sandbox/...`
   在那边根本不存在，挂上去是空目录 —— **这是 DooD 最常见的一个坑**。
2. **不用它就没有东西要「两边对上」**：容器里四个目录全是 tmpfs，`/workspace` 的内容来自
   对象存储、产物回对象存储，**没有任何长期存在的目录**（持久化早在决策 14 就收进对象存储了）。
   所以本地跑、远程跑、将来 E2B / 云函数，同一套接口。
3. `--user nobody` 写宿主机目录会撞 uid 归属问题，Linux 上尤其麻烦；tmpfs 没有这问题。

**代价照实记**：`/skills` 因此做不到设计稿 C.1 写的「只读」—— 没有 bind mount 就只能是可写 tmpfs。
不为这点收益引入 per-run docker volume（灌数据还得再起一个容器）。**这一层的安全收益本来就低**：
`/skills` 里跑的就是那个 skill 自己的代码，防它改自己没有意义。

### D. agent 侧 —— 轮子 deepagents 已造完

| # | 决策 | 依据 |
|---|---|---|
| 19 | **工具不自己设计**，用 `FilesystemMiddleware` 固定的 7 个：`ls / read_file / write_file / edit_file / glob / grep / execute`。**仅当 agent 挂了 skill 才装这个 middleware；没挂 = 一个都不装** | `deepagents/middleware/filesystem.py:799`。7 个工具**全部只调 `BackendProtocol`**。**由 middleware 自带（`self.tools`）自动并入送往 LLM 的工具清单，不走 `assemble_tools`** —— 模型「知道有 read_file」的机制与现有 calculator 相同。**按条件装配是决策 23（不用 `create_deep_agent`）的直接收益**：`graph.py:206` 的 `_REQUIRED_MIDDLEWARE` 把 `FilesystemMiddleware` 列为必需，docstring 明言移除会「静默破坏核心功能」，且专门登记在此以使 `HarnessProfile.excluded_middleware` **也排除不掉**（试图排除即 `raise ValueError`）。**故走 `create_deep_agent` 无任何参数能关掉这 7 个工具** —— MaxKB（`flow/tools.py:468`）因此在未用 skill 的对话里也渲染出 `ls`/`read_file` 块。注意 `interrupt_on` **不是**工具开关（它是 HITL 人工审批配置：工具名 → 执行前是否暂停问人），改它无济于事 |

> **`execute` 一名三指，勿混**：① `execute` **工具** —— 7 个里的最后一个，LLM 看得见、会去调；② `BaseSandbox.execute()` **方法** —— 我们要实现的那个；③ 链路 = LLM 调工具 → 工具内部调 backend 方法 → 我们的实现 → `docker exec`。
> **这 7 个是 deepagents 自己的 `StructuredTool`，不走本项目 `CoCoTool` 基类** —— 异常兜底、输出截断、超时都不会自动生效，须在 backend 实现内自行兜住。
| 20 | **唯一要写的** = 一个 `BaseSandbox` 子类，填 `execute()` + `upload_files()`，其余由基类派生 | `deepagents/backends/sandbox.py:394`（ABC，ls/grep/glob/read/edit 全部 shell 出去派生）。位置同 MaxKB `SandboxShellBackend` —— 它填宿主 subprocess，本项目填一次性容器 |
| 21 | skill 进出容器 = backend 的 `upload_files()` / `download_files()` | 同上。原「不知道怎么投递 / 怎么取回」由该接口消化 |
| 21a | **zip 传进容器、在容器内解压**（`upload_files` 送字节 → `execute("unzip …")`），**不在 web 进程内解、也不让容器自己去对象存储拉** | ① 容器自取 = 必须给它对象存储凭据，而容器里跑的是用户代码 → 等于交出整个 bucket 读写权；② 在容器内解，zip bomb 炸开时被 `--memory 256m` + tmpfs size 上限掐死；在 web 进程内解则是拿自己的进程冒险 |
| 22 | **不用 `SkillsMiddleware`**，自己拼那段 system prompt 片段（约 20 行，prompt 模板照抄它的 `SKILLS_SYSTEM_PROMPT`），清单数据：内置的从启动时扫出的内存注册表取（决策 3），用户上传的从 `skills` 表取 | `SkillsMiddleware.abefore_agent` 在 agent 一开始就调 `backend.als()` 扫 `/skills`（`middleware/skills.py`）—— **扫目录就得先有容器，与容器懒启动（决策 22a）直接冲突**。而它的核心价值「扫文件系统发现 skill」我们本就不需要：name / description 已在 DB 里 |
| 22a | **容器懒启动**：LLM 第一次调那 7 个工具中任意一个时才起容器，不在回复开头起 | 挂了 skill 的对话也未必真用沙箱，提前起是白付启动开销。启动约 1-3s（未实测），在「一轮几十秒到 5 分钟」的尺度上可接受 |
| 22b | **`SANDBOX_ENABLED` 配置 + 三层降级**：① 未挂 skill → 不装 middleware、不碰 docker；② 配置关闭 → 不装工具、prompt 不列 skill；③ 开着但 docker 连不上 → 工具返回一句人话，不抛异常 | 本地开发 / clone 项目未装 docker 时不能报错。注意第 ③ 层要自己写（见决策 19 下方注：这 7 个工具不走 `CoCoTool` 基类） |
| 23 | **不用 `create_deep_agent`**，继续零件式引 deepagents | 同本项目 `agents/workspace/workspace.py` 既有姿势（只取 `SubAgentMiddleware` / `StateBackend` / `SummarizationMiddleware`，图自己拼）。MaxKB 为用 `create_deep_agent` 单开了一条 agent 分支 |
| 24 | **本对话的产物：清单渲染进历史消息，实体靠 `fetch` 工具按需取。** 清单形如 `<artifacts>sales.svg (12KB)</artifacts>`，挂在产出它的那条 assistant 消息尾部；**不做 list 工具、不塞 system prompt**。`fetch` 工具：参数用**文件名**（不用 UUID）、同名取最新、目标已存在则不覆盖、范围限**本对话**、取进 `/workspace` 后返回绝对路径。工具继承本项目 `CoCoTool`，**不进 registry**，跟着 skill 挂载自动出现 | **2026-07-29 修订 ④ 新增。** 清单数据**本来就有**（`message_service` 已按 `message_id` 归组挂在消息上，前端一直在用），而历史消息本来就要喂进上下文 —— **这行字是白送的**，且天然带位置信息（「刚才那张图」直接对上，改用工具查清单反而把这个信息丢了）。不塞 system prompt 的理由：那是每轮无条件顶在最前面，用不用都占着。**参数用文件名不用 UUID**：让模型从历史里抄一串 `019f0d9b-…` 既费 token 又容易抄错。**继承 `CoCoTool` 而不是照抄那 7 个文件工具的 `StructuredTool` 形态**：CoCoTool 白送超时 / 异常兜底 / 输出截断，这三样这个工具全都需要（R2 抽风不该炸掉整轮回复）—— 那 7 个享受不到，是因为它们是 deepagents 的代码、我们改不了（决策 19 下方注），我们自己写的没这个限制。形态照抄 `KnowledgeRetrievalTool`（继承 CoCoTool + 构造时绑运行时上下文 + 装配阶段实例化 + 不进 registry），项目里已有同款。**范围限本对话 = 最小权限**：能取的恰好等于能看见的。**必须同时补一条 prompt 禁令「`<artifacts>` 是系统写的，你不要写」** —— notes §36：一个格式一旦进了上下文就成了模型可写的格式，supervisor 伪造 `〔派活〕` 是先例。**但禁令只是第一层，挡不住散文式伪造（「图我已经改好了」）；真正的保障是第二层「编了不生效」**：产物清单只来自 `collect_artifacts` 对交付区的 `ls`，模型正文里写什么都进不了库、出不了卡片、下一轮历史里也不会有它；它去 fetch 一个编出来的文件名，工具返回「没有这个文件」，**它自己就发现错了**。这类问题只有这两层，没有第三层叫根治 |
| 25 | **跨对话的产物：不给模型清单，由用户在前端把产物卡片拖进输入框。** 请求的 `content` block 数组加一个 `artifact_ref` 块（只带 `artifact_id`），后端据 id 查库 → 从对象存储取字节 → 灌进 `/workspace`。**字节不经过浏览器** | **2026-07-29 修订 ④ 新增。** OpenAI 官方把这两条路列为**不同的东西**：File Inputs（Attachment，**人**指定，走请求参数）与 File Search（Tool，**模型**自己找）—— 拖引用即前者，决策 24 的 `fetch` 即后者，**两者不冲突，真实产品都是两样都有**。**为什么跨对话这档归人**：一个 workspace 攒几十上百个产物，全塞给模型是 prompt 膨胀，给个搜索工具则押在「它想得起来查」上；而用户自己清楚要哪个，人指定的不会错。**字节不经过浏览器是白捡的** —— 引用的是**已经在对象存储里的产物**、不是本地文件，故不涉及 multipart、不涉及多模态，PDF / 图片 / xlsx 原样保真是天然的（字节压根没被碰过）。`content` 是 block 数组这件事早有预留：`schemas/agent/chat_schema.py` 文件头自己写着「P1 扩 ToolUseBlock、P2 扩 ImageBlock 时在这里加」。**与 P2 多模态划清界限**：拖引用是「让脚本处理这个文件」，多模态是「让模型用眼睛看这张图」，后者要图片进 `ImageBlock`，不在本片 |
| 26 | **Playground 不接这套**：不渲染产物清单、不给 `fetch` 工具、不支持拖引用 | **2026-07-29 修订 ④ 新增。** Playground 的消息不入库、产物行 `conversation_id` 为 NULL，**「本对话」在那边根本不存在**。硬接就得先回答「什么算这一次 Playground 会话」，而那个信息只活在前端内存里、服务端拿不到 —— **与其编一个近似答案，不如认下不支持**（它一贯就是刷新即丢，产物卡片不留在 §5.5 已记）。代价：Playground 里第二轮改第一轮那张图做不到，得重画；那儿是验证 skill 跑不跑得通的地方，不是干活的地方。**这里有一处行为退化要认**：local driver 下 Playground 的 `/workspace` 原本按 `user.id` 建目录、跨轮留存，随决策 14a 改成每轮清空后不再留 |

> **一次回复内的多成员共享**：supervisor 经 `SubAgentMiddleware` 派活给成员，全部发生在**同一次回复的同一张图**里 → 同一个容器、同一个文件系统。故「一支团队共用一个工作区」在**对话内部**已然成立；`/workspace` 绑 workspace 解决的是**跨对话**那一层。

---

## 3. 部署形态

```
常驻（docker-compose）
├─ postgres
├─ redis
├─ web        ← command: uv run dev
├─ worker     ← 同一镜像、不同 command（不与 web 挤一个容器：
│                容器生死绑主进程、日志混流、无法单独重启）
└─ sandboxd   ← 唯一挂 docker.sock；纯内部服务，不暴露任何对外端口

运行时动态
└─ 沙箱容器 × N   ← sandboxd 起、sandboxd 销毁，不进 compose
```

- **Docker outside of Docker**：sandboxd 挂宿主 `/var/run/docker.sock`，起的是宿主机上的**兄弟容器**，非嵌套。
- 挂 docker.sock ≈ 授予「在本机起任意容器」的权力，故 sandboxd 必须不对外 —— 这就是「进程边界」的部署形态。
- **sandboxd 从第一版就独立成进程**，`app/cli.py` 加第三个入口（`uv run sandboxd`），web 经内部 HTTP 调它。
  本地开发因此是三个进程（`dev` / `worker` / `sandboxd`）。
  > **曾一度想退成「web 进程直接调 docker、模块化留口子」，理由是本片不部署、本地 Mac 上 web 本就有全部权限。这个退让是错的**：
  > ① 「docker SDK 不进 web 进程」是 P2 已定的边界，不因本片不部署而松；
  > ② 最终要在 2C2G 机器上演示部署，部署形态必须成立；
  > ③ 判据始终是生产标准，不是「本地能跑就行」。
- **不走 SAQ**：工具调用要同步拿结果，队列是异步投递，形态不匹配。
- 本片验证只在本地 Mac 上做，但拓扑按可部署来搭。
- **开发形态：daemon 可以是远程的**（2026-07-27 修订 ③）。sandboxd 就是本机第三个终端里的
  普通进程（`uv run sandboxd`），但它指挥哪个 docker 由 `DOCKER_HOST` 决定：
  留空 = 本机 Docker Desktop；`ssh://user@服务器` = 沙箱容器起在服务器上，**开发机不必装 Docker**。
  这是 docker 官方支持的标准用法（`docker context` / `DOCKER_HOST`），代码零分支。
  **它能成立完全依赖 C.3「不用 bind mount」** —— 有 bind mount 时远程 daemon 当场失效。
  沙箱容器接专用网络、连不到 PG / Redis（决策 17），故「daemon 与数据库同机」不构成新的暴露面。
  **一个实测坑**：docker SDK 连 `ssh://` 有两条路，**必须走默认的 paramiko，不能开
  `use_ssh_client=True`** —— 后者调系统 `ssh`，能吃到 `~/.ssh/config` 的 ControlMaster 连接复用，
  但**不支持 exec 所需的劫持连接**（docker 要把 HTTP 升级成双向裸流），实测 `exec_start` 永远挂住。
  paramiko 同样读 `~/.ssh/config` 的 hostname / user / identityfile，主机别名照常生效；
  代价是没有连接复用，每条命令约 0.5s（系统 ssh 复用后是 0.1s）。**这条只影响远程开发形态** ——
  同机部署走 unix socket，paramiko 根本不参与。
  **这笔往返成本会累积**（2026-07-28 实测 **0.68s/趟**，见 §5）：一轮回复里模型读 SKILL.md、
  落数据、跑脚本、回读产物，十几条 `exec` 就是七八秒纯网络等待。**接完 web 侧自己试用时
  别把它当成代码慢** —— 它是这个开发形态的固定开销，同机部署下不存在。

---

## 4. 明确不做

| 项 | 理由 |
|---|---|
| agent 循环搬进沙箱（档 3） | 额外买到的只有故障隔离与多租户配额，是「卖沙箱型云服务」才需要的。两档共用的基础设施占大头，将来要搬地基已在 |
| 容器池 / 粘性窗口 / 排队调度 | 池化是优化不是必需。一轮 2 分钟的尺度上，容器启动 1-3s 可忽略。等跑通后用实测数据决定池子大小 |
| Skill 市场 / 外部源自动拉取 | 留字段不实现 |
| 「agent 自己装技能」工具 | 独立小切片。本片只保证数据模型与 service 层不挡路（写入口收在 service 层） |
| ~~删除同步（容器内删了文件、对象存储也删）~~ | **2026-07-26 修订 ② 后不再是一个议题** —— 不同步工作区，只收交付区的产物，没有「删除」这个状态要同步 |
| ~~条件写（If-Match）防同路径覆盖~~ | **同上，问题消失** —— object key 带 `message_id`，两轮 / 两个对话根本写不到同一个 key |
| 用户自写 tool（非 skill）跑进沙箱 | 有价值（MaxKB 即如此），但属 tool 模块的后续刀，不在本片 |
| 部署上线 | 本地 Mac 跑通即可 |

---

## 5. 未定 / 待实测替换

- **容器 512MB**（2026-07-27 修订 ③，原 256MB）：实测 `python3 -m venv` 裸解释器 15MB，
  `import pandas` 后 73MB（pandas 约 59MB）—— 但这些只是**脚本自己**吃的。
  四个可写挂载点都是 tmpfs，文件占的是同一份额度，故上限须覆盖两者之和，取 512MB。
  当前 tmpfs 分配：skills 64m / workspace 128m / outputs 128m / tmp 128m。**跑起来后用真实峰值替换。**
- **池子 3 个**：本机开发数量，非容量测算结果。
- ~~**容器启动 1-3 秒**：经验值，未实测。~~ → **2026-07-28 实测替换**
  （`scripts/probe_sandbox_startup.py`，远程 daemon `ssh://`，5 轮取中位）：

  | 段 | 中位 |
  |---|---|
  | 建容器 + 启动 | 0.75s |
  | 第一条命令跑通 | 0.71s |
  | 灌 skill 进 `/skills`（110KB） | 0.57s |
  | 销毁 | 0.22s |
  | **首次调用总阻塞**（前三段之和，即决策 22a 关心的那个数） | **2.10s** |

  **落在原估区间内，决策 11 / 22a / §4 三条都站得住**，且比原估更稳 ——
  同一轮里在**已就绪**容器上再跑一条空命令 `true` 也要 **0.68s**，说明 2.10s 的大头
  是 ssh 往返而非容器本身（前三段各含至少一趟往返）。换同机 unix socket 部署，
  这部分几乎归零，真实启动成本约在零点几秒量级，**池化的收益比原以为的更小**。
- **前端渲染**：`ls` / `read_file` 这类块在现有 chat UI 的呈现效果，跑起来再看。

---

## 5.5 已落地（本片进行中）

- **数据层 ✅**（2026-07-24）：`skills` 表（`app/models/skill.py`）+ 迁移 0017。
  顺带发现并修掉全库外键缺索引（迁移 0018，规矩已进 `docs/context.md`）。
- **内置 skill `svg-chart` ✅**（2026-07-25）：`backend/app/skills/builtin/svg-chart/`
  —— `SKILL.md` + `scripts/{_svgbase,bar,line,pie}.py`，纯标准库、MIT、产物是可看的 `.svg`。
  实测：三种图跑通、XML 合法、输出确定性（同输入同字节）、缺失值不当 0、负值柱子朝下、
  饼图喂多系列报错退出而非硬画。~~seed 入库代码推到片 4/5~~ —— 随决策 3 改判，**内置根本不入库**。
- **片 2a：agent 侧链路打通 ✅**（2026-07-26，不碰 docker）。落地件：
  - `app/services/skill/package.py` —— zip → `SKILL.md` → `skills_ref.validate()` 的胶水（**A/B 两种打包形态 + GitHub 外壳三种都归一化**；`name` 参与拼路径前自证防穿越）
  - `app/services/skill/builtin.py` —— 内置注册表（`load/list/get/resolve` + 按 name 批量取凭据），lifespan 启动时扫一次、校验失败即抛
  - `app/services/skill/prompt.py` —— `<available_skills>` XML（形状照抄 `skills_ref.to_prompt()`，但**不能调它** —— 它吃本地目录且把宿主机路径写进 `<location>`）
  - `app/services/sandbox/layout.py` —— `SandboxPaths` + 工作区铺设（`skills/`、`tmp/` 每次重铺，`workspace/` 绝不清空）
  - `app/services/skill/mount.py` —— `build_skill_mount(cfg, user, scope_id)` → `FilesystemMiddleware` + prompt 片段；**没挂 skill 返回 `None`**（决策 19 的落点）
  - `AgentConfig.builtin_skills: list[str]`；`AgentTemplate.build()` 新增 `middleware` 参数
  - **依赖新增 `skills-ref`**（Anthropic 官方参考实现）。诚实记一笔：**实测五家六份实现无一使用它，全部手写**（RAGFlow 有三份，其中两份连 YAML 库都不用、逐行 `strings.HasPrefix`）。仍然用它的唯一理由是**它是唯一一个校验失败会给出原因的实现**（`validate(dir) -> list[str]`）——其余全是「失败返回 None / 跳过 + 打日志」，因为它们的场景是「扫已有 skill 库」而非「审核用户刚传的包」。押注面只有两个函数，换回手写就是 100 行
  - **完成判据已达成**：`qwen3.7-max` 在 Playground 里自主完成 读 SKILL.md（带 `limit=1000`）→ 数据落成 JSON → **自己选了 `line.py`（时间序列，选图表格判对）** → `execute` 跑通 → 回读 SVG 自检 → 报路径。产物在 `workspace/`，跨对话保留
  - 途中修掉三个不测发现不了的问题：① `virtual_mode=True` 导致文件工具与 shell 路径空间打架；② `LoopTemplate.build` 收下 `middleware` 却不传给 `create_agent`（**签名对、类型对、不报错，只是工具全没绑上**，症状是模型把 tool call 写成纯文本）；③ 配置项被误贴进 `.env`

- **前端对接 ✅**（2026-07-26）：`GET /skills` 列表接口（读内存注册表，不查库）+ `/tools` 页第三个 Tab + ConfigPanel「资源」区第四个下拉（写 `builtin_skills`）+ `ToolUseBlock` 打磨（7 个文件工具的中文名映射 + 沙箱绝对路径缩短到挂载点起算，规则本地/容器通用）。顺带修掉一个存在一个月的类型错误：`AgentConfig` 缺 `mcp_servers` 声明，`npm run build` 一直是坏的（`vite dev` 不做类型检查所以没人发现）。

**产物回传的形态已定（未实现，2026-07-26 修订 ② 重写）**：

链路四步，每步一句话：

```
一轮结束 → ls 交付区 → 收进对象存储 → 落库带 message_id → SSE 发清单 → 前端卡片
```

- **识别 = `ls` 一个空目录**。交付区每轮新建（目录名 = `message_id`），里面有什么就是本轮产物。
  **不用快照、不用比对、不用拦 backend、不用 middleware、不用模型额外调什么工具。**
- **`ArtifactMiddleware` 这条推翻**（原文：「快照比对挂成一个 `ArtifactMiddleware`，`abefore_agent`
  拍快照 / `aafter_agent` 比对，跟着 `SkillMount` 走」）。推翻理由见 C.2 末尾：它是拿 A 的机制做 B 的事。
  连带这些中途讨论过的方案**全部作废**，不要再走回去：指纹用 hash 还是 stat、快照拍在 middleware
  还是 runner 的 `finally`、按 mtime 时间戳过滤、继承 backend 拦 `write`/`edit`/`execute` 三个写入口、
  给模型一个 `publish_artifact` 工具。**它们都是在「交付区不存在」的前提下硬猜「哪个是成果」。**
- **落库必须带 `message_id`** —— 回放要用（容器早销毁了，卡片靠 DB 记录 + 存储里的字节渲染），
  且 Workspace 的文件浏览器要按消息归组。
- **Playground 只做「消息内产物卡片」**，不做工作区文件浏览器 —— 试跑场没有「上周那份文件在哪」
  这种需求。且 Playground 消息不入库（沙盒语义），**刷新后卡片不留**，这是它一贯行为、不是缺陷。
- **Workspace 才做文件浏览器**（跨消息聚合、按消息折叠）。
- 站内预览挂账不排期，见 `issues/003-artifact-inline-preview.md`；先用下载接口的
  `Content-Disposition: inline` 让浏览器自己渲染。

- **片 2b：产物回传 ✅**（2026-07-27）：交付区目录 + `app/services/sandbox/artifact.py` 收产物 +
  `SandboxArtifact` 表与迁移 + SSE `artifacts` 帧 + 前端卡片 + 下载接口（预签名直链，
  Local 后端那条加 `Content-Security-Policy: sandbox`）。设计过程本身的教训见 notes §22–§25。
- **片 2c：workspace 接线 + 产出物面板 ✅**（2026-07-27）：supervisor 与各成员**共用同一个 mount**、
  skills 取并集（决策 12 的直接约束），挂载判据从「mount 在不在」改成 `mount.has_skills(cfg)`；
  跨对话产出物面板，SSE 帧只当刷新信号、数据仍只从接口来。见 notes §26–§28。

- **片 3a：沙箱镜像 + sandboxd ✅**（2026-07-28）：`docker/sandbox/Dockerfile`（python3 + node22 + uv，
  非 root，不预装重包 —— 实测本机 36 个真实 skill 无一带第三方依赖，依赖机制留到用户上传那一刀）；
  `app/sandbox/`（`container.py` docker 操作 + `session.py` 会话表 + `api.py` 五个端点 + `app.py` 装配），
  `uv run sandboxd` 第三个进程入口。**17 项实测全绿**：令牌鉴权、`nobody`、根只读、四个 tmpfs 可写、
  凭据注入、能出公网、退出码透传、超时 124、文件进出、销毁幂等、启动清孤儿。
  途中撞出两个不实测发现不了的坑，都已写进 C.3 / §3：`use_ssh_client` 与 exec 冲突、
  `docker cp` 与 tmpfs 互斥。

- **片 3b：LocalDocker driver 的 web 侧 ✅**（2026-07-28）：`app/services/sandbox/docker_sandbox.py`
  （`DockerSandbox` 客户端 + 懒启动 + 三层降级）、`mount.py` 按 `SANDBOX_DRIVER` 选后端、
  skill 打 tar 灌进容器、产物回收改走 backend 协议。途中的坑见 notes §35–§40：
  外层截断上限必须比内层松、懒初始化的锁要罩住整段、跨平台 shell 命令要挑两边都有的、
  验副作用要找不由被测方产生的证据（`docker events`）。

- **片 3c：产物引用链路 ✅**（2026-07-29 / 07-30 两段）：决策 14a 改判后的完整形态。
  前半（07-29，commit 936c291）= `/workspace` 每轮清空 + 产物清单渲染进视角化历史 +
  `fetch_artifact` 工具（决策 24）；后半（07-30）= **跨对话拖引用**（决策 25）。
  后半的落点：`chat_schema` / `runtime.blocks` 两层各加一个 `artifact_ref` 块类型；
  新模块 `services/sandbox/attachment.py` 两阶段（`resolve_refs` 查库校归属 + 回填展示字段，
  跑在**落库之前**；`inject_attachments` 读字节灌工作区 + 拼 `<attachments>` 标注，
  跑在**沙箱装配之后**）；assembler 回放渲染不带路径的标注；`fetch_artifact` 取值范围
  扩成「本对话产出的 ∪ 本对话拖进来引用过的」；前端原生 HTML5 拖放（不引 dnd 库）。
  **决策 26 落地为 `prepare_stream` 的一句守卫**：Playground 见到 ref 块直接 400。
  **一处产品决策（2026-07-30 用户拍板，推翻实现方案里的 400）**：没有任何参与者挂 skill 时
  （mount 为 None）拖了文件**不报错** —— 消息照发、标注如实写「本轮没有能打开文件的参与者」。
  理由：「附件只能给沙箱用」是这一刀的现状、不是永久前提，等 PDF / 图片进模型视野那一刀
  落地，同一个 `artifact_ref` 块自然多一条去处，这次的代码不返工。

- **片 3d：纯逻辑单元测试 ✅**（2026-07-30）：61 条，零 docker / 零 DB / 零网络，1.4s 跑完。
  五个文件覆盖 layout（每轮清空、交付区撞 id 当场炸）/ tar 打包拆包（只放文件条目、
  空包抛错）/ 交付区清单解析（烂输入返空不抛）/ 附件注入（撞名加后缀、三种失败都只写进
  标注）/ docker driver 降级（超时夹取、409 清 session、连不上不抛）。共用假件
  `tests/sandbox_fakes.py` **只实现被测代码真正调到的方法** —— 假件越像真的，越容易在
  真接口变了之后还静静跑绿灯。**做过变异检验**：把「每轮清空 workspace」故意改坏，
  3 条测试立刻失败，证明不是绿得没意义。

**还没做的（P5 剩余）**：

1. **用户上传 skill**（zip 层把关 + 对象存储 + CRUD + 前端）—— 本轮不做。
2. **本地文件拖进输入框**（从桌面拖 PDF / 图片，而非拖已有产物）—— 用户明确表示后续要做。
   前端管道已经铺好：`MessageInput` 的两个 drop 钩子已经能认出 `dataTransfer.types` 里的
   `Files` 并拦掉浏览器默认行为（不拦会导航去打开那个文件），目前只弹一句「暂不支持」。
   那一刀要补的是**上传那半段**：multipart → files 表 → 拿 id 挂消息，形状与决策 25 同构。
   与 P2 多模态划清界限的那条仍然成立（让脚本处理 vs 让模型用眼睛看）。

**已知限制（明确不修，记录在此免得日后当 bug 查）**：

- **同名文件的取回歧义**：`fetch_artifact` 按文件名取、同名取最新。范围扩到跨对话之后，
  同一个名字在候选池里可能有好几份（实测本机 `chart.svg` 就横跨三个对话）。
  触发条件窄：得同时满足「拖进来的是旧的」+「本对话自己也产过同名的更新版本」；
  后果可恢复（模型读到内容不对会自己发现），工具返回里也有一句「有 N 个同名，这是最新的」。
  **真解法是让标识天生唯一** —— 标注渲染成 `chart.svg#a1b2c3d4`（仅在真撞名时才加后缀）、
  `fetch_artifact` 支持精确匹配。思路对齐真实产品（OpenAI 用 `file_id`、code interpreter 用
  `/mnt/data/<路径>`，**它们引用的东西天生唯一，我们却拿文件名当标识**）。
  要动 assembler + 工具 + prompt 三处，是个小切片不是 bug 修复，收尾期不做。
- **消息气泡里的产物卡片不可拖**（`ArtifactCard`）：只有右栏产出物面板的行能拖进输入框。
  产品判断（用户 2026-07-30）：那个位置本来就不需要拖拽 —— 消息里那张卡是「刚交付的成果，
  点开看看」，跨对话取用是面板的职责。
- **`resolve_refs` 的查库路径没有单测**：它要 DB fixture，属于集成那一层，不在纯逻辑那批里。
  目前由手工验收覆盖。

## 6. 范围与排期

**P5 = 抽象层（driver 可替换）+ LocalDocker driver + skill 存储与装配链路 + 本地跑通。**

roadmap 原写 2 天 → 实际 **2-3 天**。

**完成判据**（沿用 roadmap）：一个带脚本的 Skill 能被 agent 调用、在容器内执行、产物回传，宿主机无副作用。
