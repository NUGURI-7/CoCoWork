# P5 · Skill 执行 + 沙箱 — 设计决策（v1，2026-07-24 冻结）

> 本文件是 P5 的**决策记录**，不是实现方案。每条决策附依据（源码路径或推导过程），
> 便于日后复核；没有依据的条目显式标注为「产品决策」或「估算，待实测替换」。
> 实现方案另出。

---

## 0. 定位

做 Skill 的**执行能力**：一个带脚本的 Skill 能被 agent 调用、在容器内执行、产物回传，宿主机无副作用。

**一句话架构**：agent 循环留在应用进程，沙箱是一次性 Docker 容器；一次完整回复借还一个容器，
容器内所有命令走 `docker exec` 靠文件传递产物，回复结束把 `/workspace` 的变更按文件同步回对象存储、销毁容器。
工作区状态绑 **workspace**（跨对话可见），不绑容器、不绑对话。

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
| 3 | 两个来源：**内置**（随代码分发，`backend/app/skills/builtin/<name>/`）+ **用户上传**。**两者共用同一条入库路径** —— 内置只是启动时 seed 进表的种子数据，同样 per-user、同样可删改 | 刻意不做「共享的内置行」：那会让权限判断分叉，且共享行挂不上 per-user 的凭据。放 `app/` 下是硬约束 —— `pyproject.toml:66` 是 `packages = ["app"]`，放外面构建镜像时带不进去、部署即 seed 失败。**曾一度决定「v1 不做内置」**（理由是自造的是玩具、Anthropic 官方那批是 Proprietary 不能分发），后因自写的 `svg-chart`（MIT、零依赖、产物是可看的 SVG）合格而收回 |

### B. Skill 怎么存

| # | 决策 | 依据 |
|---|---|---|
| 4 | 用户上传的：**DB 存元数据 + 对象存储存 zip 本体**，复用现有 `storage` 抽象（R2/Local）。表里只放 key，不存字节 | Dify `agent_drive_files` 表是路径 KV、**从不存字节**；MaxKB File 表存 zip；Letta block 表 — 三家一致。本项目 Document 表已是此形态 |
| 5 | **独立 `skills` 表**，不塞进 tool 表 | 反面教材 = MaxKB `tool` 表的 `code` 字段：CUSTOM 存 Python / SKILL 存 File id / MCP 存别的，一字段三语义、大量列对某类型恒空。正面 = 本项目 `MCPServer` 已独立成表 |
| 6 | `source_type`（builtin / user）**只作来源溯源**，用于 UI 区分与 seed 幂等判断 —— **不是权限位，两者都可删改** | 原设想是「builtin 不可删改」（仿 Letta block 的 `read_only`，`core_tool_executor.py:320`），随决策 3 改成「内置也走同一条入库路、也是 per-user 行」后失去意义 |
| 7 | `AgentConfig.skills: list[UUID]` **保持 UUID 不变** | skill 是 DB 实体，同 KB / MCP；只有内置工具用 str name |
| 8 | 写入口**收在 service 层**；沙箱与 agent 永不持有 DB 凭据 | Letta `core_memory_append` 走 manager + `actor` + `read_only` 校验；Dify agent stub 用 JWE 令牌回调应用；OpenHands session key 仅 RUNNING 时有效 — 三家一致 |
| 9 | 流通性 = **上传入库 ✅ / 导出 ✅**；外部源导入、市场 **留字段不实现** | 导出 = 拉归档，零成本（原「不做」已收回）。Letta `SkillSchema.source_url`、OpenHands `MarketplaceRegistration` 证明分发是数据模型的一部分，故留字段 |
| 9a | 上传侧校验：**zip 大小上限** + **必须含 `SKILL.md`** + **frontmatter 合规**（见下）+ **成员路径不含 `..` / 不以 `/` 开头** | 末项抄 MaxKB `flow/tools.py:412`（`if ".." in member or member.startswith("/"): raise`，这段它做对了）。**其价值是「早报错 + 不依赖工具默认行为」，不是「不做会被黑」** —— 2026-07-25 实测：Python `zipfile.extractall` 已自动剥掉 `..` 与前导 `/`（CPython 文档明载），恶意条目落在目标目录内而非穿出去。但默认行为是**静默剥离**（用户不知道包有问题），且我们在容器内用 `unzip` 解压（决策 21a）时保护取决于那个 `unzip` 的版本与参数，已不在 Python 的保护范围。**大小上限挡不住 zip bomb**（特征是文件小、解开巨大），那一层靠容器的 `--memory` + tmpfs size 兜 |
| 9b | frontmatter 校验按 **Agent Skills 规范原文**（https://agentskills.io/specification ，2026-07-25 已核对原文，非转述）：`name` 必填、1-64 字符、仅小写字母数字与连字符、不以 `-` 起止、无连续 `--`、**须等于父目录名**；`description` 必填、1-1024 字符；`license` / `compatibility`(≤500) / `metadata` / `allowed-tools` 可选 | 校验动机是四件具体事，不是「为了合规」：① 缺 `name`/`description` 则 prompt 片段拼不出来；② `name` 会进 prompt 且被当目录名，含空白或 `/` 会出诡异问题；③ 长度上限防单个描述把 prompt 撑爆；④ 对齐规范意味着聚合站下载的包能直接用（官方另有 `skills-ref validate` 工具）。**「须等于父目录名」并非我们的正确性必需**（deepagents 单独存 `path`、我们单独存 `storage_key`，都不靠 name 找文件），仍硬校验只为对齐规范 —— 曾以「否则找不到文件」为理由，该理由已收回 |
| 9c | **prompt 膨胀不是问题，v1 全部常驻**；真挂多了再上 trigger | 规范「渐进披露」节自述：metadata（`name`+`description`）**约 100 tokens/skill**，启动时全部加载；1024 是硬上限非目标（Anthropic pdf skill 描述约 250 字符）。且挂载是用户显式选的（`AgentConfig.skills`），非全库注入 —— 与「挂 5 个工具就常驻 5 份 schema」同量级，工具 schema 通常更长。将来若需按需注入，照 OpenHands 的 `KeywordTrigger` / `TaskTrigger`（用户消息命中关键词才注入），决策 22 自拼 prompt 的形态天然容得下 |

**表结构草案**（实现时定稿）：
```
skills
├── created_by      FK User
├── name            SKILL.md 的 name（LLM 可见标识）
├── description     SKILL.md 的 description（进 prompt 供判断）
├── source_type     builtin | user   ← 来源溯源（非权限位）
├── storage_key     对象存储 zip 的键
├── skill_metadata  jsonb：原包文件清单等（抄 Dify `skill_metadata`）
├── enabled
└── 时间戳
```

### C. 沙箱怎么跑

| # | 决策 | 依据 |
|---|---|---|
| 10 | 执行**跨进程边界**、Docker 容器隔离；web 进程不碰 docker | §1.3；且与 P2 既定「docker SDK 绝不能进 web 进程」同一条边界 |
| 11 | **一次性容器**：起 → 跑 → `docker rm`。不用 restart 复用（省的几秒不值），池化推后 | 销毁式清理使「清理漏网 = 跨用户数据泄露」这类 bug 不存在。RAGFlow 池化可行的前提是 read-only + tmpfs（清理近乎免费），与本项目取舍不同 |
| 12 | **借还粒度 = 一次完整回复**（一条用户消息 → agent 与 LLM 转 N 圈 → 吐完回复）。轮内所有命令打进**同一容器** | 若按单条命令借还，一轮十几步就要解包/打包十几次，方案作废 |
| 13 | 命令执行 = **`docker exec`**，不上容器内守护进程 | 守护进程唯一多买到的是 shell 会话态（cwd 延续 / 后台常驻），Dify 需要（tmux 长会话）、OpenHands 需要（`npm run dev` 后测网页）；本项目 skill 是跑完即止的脚本，用不上。**产物跨命令传递靠文件、与此选择无关**（文件在容器磁盘，活得比 shell 进程久） |
| 14 | **工作区状态绑 workspace**（不绑容器、不绑对话）：状态活在对象存储，容器随时可销毁 | OpenHands `sandbox/workspace_archive.py`：删容器前把工作区传对象存储，「让 agent 的工作在沙箱被删除后仍存活」。**绑定粒度**：Letta 绑 agent（MemFS）、Dify 绑 `agent-<agent_id>`（drive_ref）—— 本项目 workspace 就是那个「持久实体」（自带 supervisor + 招募成员 + 跨多个 conversation），故映射到 workspace 而非 conversation。**曾误判为「无先例可抄」，是因为把 workspace 当成了「装对话的容器」而非实体** |
| 15 | 带 key 的 skill：**Fernet 加密存 DB → 运行时解密 → `docker run -e` 启动注入** | 同本项目 Provider API key、MCPServer headers 既有做法。注入时机是「起容器时」，故与命令怎么跑无关 |
| 16 | 容器加固：`--read-only` + tmpfs + `--user nobody` + `--memory 256m` + `--cpus`；装 Python + Node | 直接抄 RAGFlow `executor_manager/core/container.py:82` 的 `create_container` 参数 |
| 17 | **网络**：沙箱容器接**专用 docker network**（网络内只有沙箱自己，PG / Redis / web 都不在）→ 能出公网、连不到内部服务。**外加一条防火墙规则**拦云元数据地址：`iptables -I DOCKER-USER -d 169.254.169.254 -j DROP` | 靠网络拓扑而非 iptables 规则集，Mac / Linux 一致。**元数据地址必须单独拦** —— 它返回的是可直接调云 API 的 IAM 临时凭据，不是配置信息；Capital One 2019 即由 SSRF 打到该地址窃取凭据、泄露约 1 亿条客户数据（AWS 因此推出 IMDSv2）。**RAGFlow 的做法不可照搬**：它靠 AST 静态分析禁 `socket`/`http.client`/`os`/`subprocess` 等 import（`services/security.py`），那是纯计算节点的做法，skill 要调外部服务、禁不得 |
| 18 | **抽象层 + 多 driver**：首发 LocalDocker；远程执行机 / E2B / 阿里云 FC **留实现位不做**。gVisor 是 Linux 上的启动参数，代码不动 | RAGFlow 5 provider、Letta 3、OpenHands 3 — 四家一致。同本项目 Storage(R2/Local)、Splitter、Parser 既有姿势 |

#### C.1 容器目录布局

```
/skills      ← 挂载的 skill 解压于此（只读）
/workspace   ← 持久区：同步回对象存储，跨对话可见
/tmp         ← 本轮临时区（tmpfs 内存盘）：容器销毁即弃，不同步
```

除这三处外整个文件系统 `--read-only`。**临时区直接用 `/tmp`**（Linux 标准语义，脚本作者与 LLM 都天然知道它会被清掉，无需在 prompt 里额外解释；RAGFlow 亦挂 `--tmpfs /tmp`）—— 不自造 `/scratch` 之类的名字。

#### C.2 同步机制：按文件、不按整包

**object key = `sandbox/{workspace_id}/{相对 /workspace 的路径}`，一个文件一个对象。**
```
/workspace/plan.md         ←→ sandbox/{wsid}/plan.md
/workspace/data/sales.csv  ←→ sandbox/{wsid}/data/sales.csv
```

**key 里不含 conversation_id** —— 一放进去对话 B 就找不到对话 A 写的文件，等于退回「一对话一份文件系统」。

**为什么不能按整包**：整包是 read-modify-write，必然丢更新 ——
对话 A、B 各自拉走同一份快照，A 传回整包后 B 再传回它那份旧快照，A 的改动被覆盖。
分子目录（`shared/` + `conv-x/`）**不解决**：冲突发生在整包层面，不在文件层面。

**只回传变更的文件**，靠一份「进门快照」判断：挂载时把每个文件记成 `{相对路径: 内容指纹}`
（指纹 = 内容的 hash，内容改一个字节指纹就完全不同）；销毁时遍历 `/workspace` 重算，跟进门那份比 ——

| 情况 | 动作 |
|---|---|
| 快照里没有 | 新文件 → 上传 |
| 有，指纹不同 | 已修改 → 上传 |
| 有，指纹相同 | 未改动 → 不传 |
| 快照里有、文件已不存在 | 删除 → **v1 不处理** |

**不加锁、不为一致性排队**（容器池的排队是另一回事）：两个对话写不同文件天然无冲突；
撞同一 key 是语义冲突，**v1 后写赢 + 记日志**。条件写（If-Match）留后续 —— 现在要求它会逼
`storage` 抽象长出一个 Local 后端做不到的残缺能力。

**安全边界 = workspace 前缀**，无新增风险（workspace 归属校验既有）。两条必须做的防护：
① `workspace_id` 只能服务端取，绝不受 skill / LLM 影响；
② 相对路径防穿越（`../` 逃出前缀）—— 复用 Local storage 后端既有的路径穿越防护。

### D. agent 侧 —— 轮子 deepagents 已造完

| # | 决策 | 依据 |
|---|---|---|
| 19 | **工具不自己设计**，用 `FilesystemMiddleware` 固定的 7 个：`ls / read_file / write_file / edit_file / glob / grep / execute`。**仅当 agent 挂了 skill 才装这个 middleware；没挂 = 一个都不装** | `deepagents/middleware/filesystem.py:799`。7 个工具**全部只调 `BackendProtocol`**。**由 middleware 自带（`self.tools`）自动并入送往 LLM 的工具清单，不走 `assemble_tools`** —— 模型「知道有 read_file」的机制与现有 calculator 相同。**按条件装配是决策 23（不用 `create_deep_agent`）的直接收益**：`graph.py:206` 的 `_REQUIRED_MIDDLEWARE` 把 `FilesystemMiddleware` 列为必需，docstring 明言移除会「静默破坏核心功能」，且专门登记在此以使 `HarnessProfile.excluded_middleware` **也排除不掉**（试图排除即 `raise ValueError`）。**故走 `create_deep_agent` 无任何参数能关掉这 7 个工具** —— MaxKB（`flow/tools.py:468`）因此在未用 skill 的对话里也渲染出 `ls`/`read_file` 块。注意 `interrupt_on` **不是**工具开关（它是 HITL 人工审批配置：工具名 → 执行前是否暂停问人），改它无济于事 |

> **`execute` 一名三指，勿混**：① `execute` **工具** —— 7 个里的最后一个，LLM 看得见、会去调；② `BaseSandbox.execute()` **方法** —— 我们要实现的那个；③ 链路 = LLM 调工具 → 工具内部调 backend 方法 → 我们的实现 → `docker exec`。
> **这 7 个是 deepagents 自己的 `StructuredTool`，不走本项目 `CoCoTool` 基类** —— 异常兜底、输出截断、超时都不会自动生效，须在 backend 实现内自行兜住。
| 20 | **唯一要写的** = 一个 `BaseSandbox` 子类，填 `execute()` + `upload_files()`，其余由基类派生 | `deepagents/backends/sandbox.py:394`（ABC，ls/grep/glob/read/edit 全部 shell 出去派生）。位置同 MaxKB `SandboxShellBackend` —— 它填宿主 subprocess，本项目填一次性容器 |
| 21 | skill 进出容器 = backend 的 `upload_files()` / `download_files()` | 同上。原「不知道怎么投递 / 怎么取回」由该接口消化 |
| 21a | **zip 传进容器、在容器内解压**（`upload_files` 送字节 → `execute("unzip …")`），**不在 web 进程内解、也不让容器自己去对象存储拉** | ① 容器自取 = 必须给它对象存储凭据，而容器里跑的是用户代码 → 等于交出整个 bucket 读写权；② 在容器内解，zip bomb 炸开时被 `--memory 256m` + tmpfs size 上限掐死；在 web 进程内解则是拿自己的进程冒险 |
| 22 | **不用 `SkillsMiddleware`**，自己拼那段 system prompt 片段（约 20 行，prompt 模板照抄它的 `SKILLS_SYSTEM_PROMPT`），清单数据从 `skills` 表取、内置 skill 启动时扫一次 | `SkillsMiddleware.abefore_agent` 在 agent 一开始就调 `backend.als()` 扫 `/skills`（`middleware/skills.py`）—— **扫目录就得先有容器，与容器懒启动（决策 22a）直接冲突**。而它的核心价值「扫文件系统发现 skill」我们本就不需要：name / description 已在 DB 里 |
| 22a | **容器懒启动**：LLM 第一次调那 7 个工具中任意一个时才起容器，不在回复开头起 | 挂了 skill 的对话也未必真用沙箱，提前起是白付启动开销。启动约 1-3s（未实测），在「一轮几十秒到 5 分钟」的尺度上可接受 |
| 22b | **`SANDBOX_ENABLED` 配置 + 三层降级**：① 未挂 skill → 不装 middleware、不碰 docker；② 配置关闭 → 不装工具、prompt 不列 skill；③ 开着但 docker 连不上 → 工具返回一句人话，不抛异常 | 本地开发 / clone 项目未装 docker 时不能报错。注意第 ③ 层要自己写（见决策 19 下方注：这 7 个工具不走 `CoCoTool` 基类） |
| 23 | **不用 `create_deep_agent`**，继续零件式引 deepagents | 同本项目 `agents/workspace/workspace.py` 既有姿势（只取 `SubAgentMiddleware` / `StateBackend` / `SummarizationMiddleware`，图自己拼）。MaxKB 为用 `create_deep_agent` 单开了一条 agent 分支 |

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

---

## 4. 明确不做

| 项 | 理由 |
|---|---|
| agent 循环搬进沙箱（档 3） | 额外买到的只有故障隔离与多租户配额，是「卖沙箱型云服务」才需要的。两档共用的基础设施占大头，将来要搬地基已在 |
| 容器池 / 粘性窗口 / 排队调度 | 池化是优化不是必需。一轮 2 分钟的尺度上，容器启动 1-3s 可忽略。等跑通后用实测数据决定池子大小 |
| Skill 市场 / 外部源自动拉取 | 留字段不实现 |
| 「agent 自己装技能」工具 | 独立小切片。本片只保证数据模型与 service 层不挡路（写入口收在 service 层） |
| 删除同步（容器内删了文件、对象存储也删） | v1 不做。只做新增 / 修改的回传 |
| 条件写（If-Match）防同路径覆盖 | Local storage 后端做不到，现在要求会逼抽象层长出残缺能力。v1 后写赢 + 记日志 |
| 用户自写 tool（非 skill）跑进沙箱 | 有价值（MaxKB 即如此），但属 tool 模块的后续刀，不在本片 |
| 部署上线 | 本地 Mac 跑通即可 |

---

## 5. 未定 / 待实测替换

- **容器 256MB**：实测 `python3 -m venv` 裸解释器 15MB，`import pandas` 后 73MB（pandas 约 59MB）。
  纯脚本 128MB 够，数据分析类会偶发 OOM，故取 256MB。**跑起来后用真实峰值替换。**
- **池子 3 个**：本机开发数量，非容量测算结果。
- **容器启动 1-3 秒**：经验值，未实测。
- **前端渲染**：`ls` / `read_file` 这类块在现有 chat UI 的呈现效果，跑起来再看。

---

## 5.5 已落地（本片进行中）

- **数据层 ✅**（2026-07-24）：`skills` 表（`app/models/skill.py`）+ 迁移 0017。
  顺带发现并修掉全库外键缺索引（迁移 0018，规矩已进 `docs/context.md`）。
- **内置 skill `svg-chart` ✅**（2026-07-25）：`backend/app/skills/builtin/svg-chart/`
  —— `SKILL.md` + `scripts/{_svgbase,bar,line,pie}.py`，纯标准库、MIT、产物是可看的 `.svg`。
  实测：三种图跑通、XML 合法、输出确定性（同输入同字节）、缺失值不当 0、负值柱子朝下、
  饼图喂多系列报错退出而非硬画。**它的 seed 入库代码推到片 4/5（上传流程）一起做**，
  当下先当 2a 验证链路的素材用。

## 6. 范围与排期

**P5 = 抽象层（driver 可替换）+ LocalDocker driver + skill 存储与装配链路 + 本地跑通。**

roadmap 原写 2 天 → 实际 **2-3 天**。

**完成判据**（沿用 roadmap）：一个带脚本的 Skill 能被 agent 调用、在容器内执行、产物回传，宿主机无副作用。
