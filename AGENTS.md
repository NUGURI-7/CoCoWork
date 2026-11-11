# CoCoWork 项目指南

本文件适用于 CoCoWork 仓库。用户在当前对话中的明确要求优先于本文件。
本文件整理自项目 `CLAUDE.md`，适用于 Codex；原文件保留供 Claude Code 使用。
全局交流偏好由用户级 `AGENTS.md` 管理，这里只记录项目约定。

## 项目上下文

- 开始新任务时，先读取 `docs/context.md`，了解当前实现与已有决策。
- 涉及办公工作台的产品设计或用户端改动时，读取 [产品规则](PRODUCT.md)，按其中的服务对象、入口和自定义边界设计。
- 当前状态以 `docs/context.md` 为入口，近期开发记录查看 `docs/weekly.md`；按任务需要继续读取相关文档和代码。
- 文档中的远期愿景不等于已实现功能；依赖版本以项目配置与锁文件为准。
- 有意义的改动影响项目现状时，更新 `docs/context.md` 对应段落；优先重写摘要，避免无限追加。开发周报按 `docs/weekly.md` 既有格式维护。
- 纯讨论、只读检查或不影响项目理解的小改动，无需更新上下文文档。

## 开发与审批

- 写代码前，先简短说明方案，等待用户同意。需求缺少关键细节时先澄清。
- 架构设计、模块搭建、技术选型等复杂任务，先讨论方向，再给具体代码方案审批，通过后才能落盘。
- **后端代码**：落盘前给用户审阅完整改动。已有文件说明路径与行号，展示「原来 → 改后」及必要上下文；新增文件给完整全文。解释为什么改这里、调用关系和影响，再用自然语言说明执行顺序与失败处理。用户批准后才能写入。
- **前端代码**：落盘前只说明功能、涉及文件与影响，获得许可后直接写；用户不审阅前端代码，不主动贴前端代码。
- **单元测试**：编写和执行不必单独申请，汇报有意义的结果。
- 不把已经获批的工作拆成重复确认；用户改变范围或关键方案发生变化时，再说明变化并确认。
- 优先采用成熟、适合实际需求的方案。代码首版应具备合理的架构、命名、类型和异常处理，不用临时占位或「以后再补」替代必要实现。
- 小步迭代按任务范围划分，每次交付应完整可用。
- 说明模型、配置和阈值时，区分代码默认值、实测结果与实际部署状态，不把其中一种当作另一种。

## 技术与目录

- 后端：FastAPI、Tortoise ORM、PostgreSQL / pgvector、Redis、LangGraph、SAQ；代码在 `backend/app/`。
- 后端业务入口：`api/routes/` 路由、`models/` 数据模型、`schemas/` 请求响应结构、`services/` 业务逻辑、`agents/` Agent 运行与编排、`tasks/` 异步任务、`core/` 通用设施。
- 后端内部导入统一使用 `from app.xxx`；Python 项目配置在 `backend/pyproject.toml`，运行后端命令时进入 `backend/`。
- 前端：React、TypeScript、Vite、Tailwind CSS v4、shadcn/ui、TanStack Router、Zustand；代码在 `frontend/src/`，使用 npm 管理依赖。
- 前端按既有结构放入 `components/`、`pages/`、`routes/`、`stores/`、`api/`、`request/`、`types/`、`lib/`。
- 常用命令：后端在 `backend/` 执行 `uv run dev`、`uv run worker`、`uv run pytest`；前端在 `frontend/` 执行 `npm run dev`、`npm run build`。
- 按改动选择必要检查；注意前端 `npm run lint` 自带 `--fix`，`npm run format` 会写文件，不能当成只读检查。

## 数据库迁移

- 禁止手写迁移文件正文。先修改 model，再在 `backend/` 执行 `uv run tortoise makemigrations -n <名称>`，由 CLI 生成并交给用户审阅。
- 不引入 Aerich 替代项目现有的 Tortoise 迁移机制。
- 外键索引遵循项目约定：`ForeignKeyField` 显式声明所需 `db_index=True`；已有复合索引覆盖的例外按现有设计判断，避免重复建索引。

## 前端约定

- 静态图标统一用 `lucide-react`，动态 loader / spinner 用 `ldrs`；不手写 SVG，不新增其他图标库。第三方组件内部图标保留，只通过 CSS 统一颜色。
- 仅在无法注入 DOM 的伪元素等场景使用 SVG data URI mask，path 必须来自 Lucide 官方图标。
- Tailwind 使用 v4 的 CSS 配置，遵循 `frontend/src/app.css` 的设计 token；水平方向裁剪优先使用 `overflow-x-clip`，避免影响垂直弹层。
- 品牌色、可点击卡片沿用既有 token 和 `card-interactive` 工具类，细节见 `docs/context.md` 和相关设计文档。
- 添加 shadcn 组件时在 `frontend/` 执行 `npx shadcn@latest add <组件>`。
- 路由生成文件 `routeTree.gen.ts` 由插件维护，不手改、不提交。
- 前端 UUID 统一使用 `uuid` 库，不使用 `crypto.randomUUID()`，兼容 HTTP 裸 IP 部署。

## 学习笔记

- 用户说「记笔记」时，先读取 `notes/README.md` 的目标与组织方式。
- 是否记录以复习自测、防遗忘、面试备忘为标准；不记录助手思维过程和交流方式。
- 先列出准备记录的条目供用户审批，通过后再落盘。
- 优先补充既有模块：`notes/backend/<模块>/` 或 `notes/frontend/<模块>/` 中的 `notes.md`、`qa.md`；沿用 frontmatter、TL;DR、编号要点和 QA 格式，避免重复和无必要的新目录。

## Git 提交

- 仅在用户要求或授权提交时执行提交。
- 格式为 `<type>: <英文标题>`，标题不超过 70 字符；type 使用 `feat`、`fix`、`refactor`、`style`、`chore`、`docs`。
- 正文先列中文要点，再写对应英文摘要；不列文件路径清单。一次提交聚焦一件事，要点超过 8 条时考虑拆分。
- 不沿用 `CLAUDE.md` 中的 Claude / Anthropic 署名模板；如添加协作者署名，必须与实际执行者一致，不虚构模型版本或邮箱。
