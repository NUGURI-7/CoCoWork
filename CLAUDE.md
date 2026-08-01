## Global User Preferences

1. Prefer production-grade, industry-standard solutions over quick fixes or ad hoc hacks. When a widely accepted standard approach exists, use it instead of inventing a custom workaround.
2. 所有任务动手前都需要先描述步骤/方案，等用户审批后再编写代码。对于架构设计、模块搭建、技术选型等复杂任务，代码方案需额外经过一轮审批后才能写入文件。
3. If the user's request is ambiguous or missing key details, ask clarifying questions before writing code.
4. **每次开始新对话时，必须先读取 `../CODING-STYLE.md`（Amoy 根目录），这是项目编码规范，严格遵循其中的代码风格、架构模式和设计思维。如果你是 Claude 模型则不用读（这些规范本来就是你写的）。**
5. 每次开始新任务时，如果存在 `docs/context.md`，先读取它。
6. 每次完成有意义的项目改动后，更新 `docs/context.md`，同步最新的当前状态。
7. 保持 `docs/context.md` 精简：优先重写摘要，只保留最近迭代，并将更早内容压缩进历史摘要。
8. **`记笔记` 触发词**：当我说「记笔记」时，把当前对话里值得沉淀的概念 / 决策 / 踩坑写进学习笔记。**判断值不值得记，只看 `notes/README.md` 定的三条目标：复习自测 / 防遗忘 / 面试备忘** —— 即「将来我复习这个项目、或别人针对这个项目问起时用得上」，**不是**「离开这个项目还成立的通用道理」；沟通方式、Claude 自己的思维过程一律不记。笔记模块固定在项目根目录下的 `notes/`（`notes/backend/<模块>/` 或 `notes/frontend/<模块>/`，每个模块含 `notes.md` + `qa.md`，遵循既有 frontmatter + TL;DR + 编号要点 / QA 风格），**不用每次现找目录**。写之前**先列出「打算记哪些条目」让我审批，审批通过再落盘**，不要直接写。优先追加到已有模块笔记、避免重复，不轻易新建目录。
9. **代码默认生产级最终版**：每次落盘的首版即架构 / 命名 / 扩展性 / 类型 / 异常一次到位；不分"先简后繁"、不写阶段化占位（P0/P1、# TODO 这版先这样）。小步迭代是任务分段，不是代码风格分段。

## 代码分工（谁动文件）

**所有代码都由 Claude 落盘（Write/Edit），用户不手敲。** 但前后端的审批方式不同：

**后端 —— 必须看代码。** 落盘前把完整代码贴在对话里，按下面「给代码的方式」带用户读一遍，用户点头之后才动文件。**未经审批不许落盘。**

**前端 —— 不看代码。** 落盘前只说清「要做什么、动哪几个文件」，得到许可即可直接写，**不要把前端代码贴出来**（用户不 review 前端）。

**单元测试**例外：写完直接跑，只汇报结果，不必事先申请。

**数据库迁移**：禁止手写迁移文件正文 —— 先改 model，再 `uv run tortoise makemigrations -n xxx` 用 CLI 生成，生成结果给用户过目。

拿不准归哪类时，先问，不要默认落盘。

### 给代码的方式（不给孤立函数）—— 只适用于后端

给我看后端代码时，按「我要顺着你的话在文件里找到它」来写，不要甩一段孤立函数让我自己找位置：

1. 先说**打开哪个文件、改哪一段**（带行号锚点）。
2. 已有文件一律给「**原来长这样 → 改成这样**」，前后留几行原代码当路标；只有新增文件才给完整全文。
3. 说清**为什么改这里**，以及它跟谁有关系（谁调它、参数从哪来、改完谁受影响）。

目的：后端代码全部由 Claude 落盘，所以「审」是我唯一一次看见它的机会 ——
我是这个项目唯一的维护者，出了 bug 得自己知道去哪儿看。审不明白等于没写。

# CoCoWork — Claude Code 指南

> **AI Agent 管理平台**（暂定方向，随开发推进持续演化）：基于 LangGraph + FastAPI + PostgreSQL（pgvector）+ Redis 构建后端，React 19 + shadcn/ui 构建前端。核心能力包括：多 Agent 编排与调度、RAG 混合检索（向量 + 全文检索 + 重排序）、Prompt 版本管理、Skill 技能市场、知识库管理；支持语音交互（ASR/TTS）与视觉理解多模态输入输出；提供多层 RBAC 权限管控与资源隔离。定位为可管理、可编排、可扩展的一站式 Agent 平台。

## 项目结构

```
CoCoWork/
├── backend/                  # FastAPI + Tortoise ORM + PostgreSQL + Redis + LangGraph + SAQ
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI 应用入口
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/       # 路由模块，按业务域拆分
│   │   ├── models/           # Tortoise ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应 schema
│   │   ├── services/         # 业务逻辑层
│   │   ├── core/             # 配置、认证、Redis、异常、中间件、依赖等通用基础设施
│   │   │   ├── config.py     # 全局配置（DB、Redis、JWT 等）
│   │   │   └── security.py   # 认证 / 鉴权
│   │   ├── db/
│   │   │   └── postgresql.py # TORTOISE_CONFIG + PostgreSQLClient（非 FastAPI 上下文用）
│   │   ├── agents/           # LangGraph Agent 定义
│   │   └── tasks/            # SAQ 异步任务
│   ├── migrations/           # Tortoise ORM 迁移文件
│   ├── tests/
│   └── pyproject.toml        # 后端依赖管理（uv）
├── frontend/                 # React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui (Radix UI)
│   ├── src/
│   │   ├── components/       # 通用 UI 组件
│   │   │   └── ui/           # shadcn/ui 组件（button/card/form/input/label/sonner...）
│   │   ├── pages/            # 页面级组件（Login.tsx / Home.tsx 等）
│   │   ├── routes/           # TanStack Router 文件式路由（__root / index / login / register / $）
│   │   ├── stores/           # Zustand 状态管理
│   │   ├── api/              # 后端 API 调用，按业务域拆分
│   │   ├── request/          # Axios 实例 + 拦截器
│   │   ├── types/            # 类型定义
│   │   ├── lib/              # 工具函数（cn 等）
│   │   ├── main.tsx          # 入口：createRouter + RouterProvider
│   │   └── app.css           # Tailwind v4 入口 + design tokens
│   ├── public/               # 静态资源
│   ├── routeTree.gen.ts      # TanStack Router 自动生成（gitignored）
│   ├── package.json
│   └── tsconfig.json
├── docs/                     # 项目文档（context.md、design-tokens.md、migrations.md 等）
└── CLAUDE.md
```

### 后端 Import 约定

- `pyproject.toml` 位于 `backend/` 目录下，不在 monorepo 根目录
- 所有后端内部 import 使用 `from app.xxx` 形式，例如 `from app.models.user import User`
- 运行后端命令时在 `backend/` 目录下执行

## 图标规范

**静态图标统一使用 `lucide-react`（shadcn/ui 生态默认）；动态 loader / spinner 类动画使用 `ldrs`。禁止手写 SVG 或引入其他图标库。**

> **例外**：第三方组件库内部自带的图标，保持原样，不做替换。只通过 CSS 统一颜色即可。

### React 组件中使用

```tsx
import { Plus, Pencil, Settings } from 'lucide-react'

<Pencil size={16} />
```

### CSS mask-image 方式（适合伪元素场景）

仅当无法注入 DOM 时（如 `::before` 内），才用 SVG data URI mask，且 SVG path 必须从 Lucide 官方图标提取，不自行绘制。

## Tailwind CSS 注意事项

- 使用 Tailwind v4（CSS-based config，无 tailwind.config.js），支持 variant 叠加，如 `group-data-[collapsed]/sidebar:group-hover:opacity-100`
- `overflow-x-clip`（非 `overflow-x-hidden`）：只裁剪水平方向，不影响垂直方向的 Popover / dropdown 弹出

## UUID 生成约定

**统一使用 `uuid` 库，禁止 `crypto.randomUUID()`。** 后者属于 Web Crypto API，仅在 secure context（HTTPS / localhost）下可用，HTTP 裸 IP 部署会直接抛 `TypeError: crypto.randomUUID is not a function`。

```ts
import { v4 as uuidv4 } from 'uuid'

const id = uuidv4()
```

## Git 提交规范

### Commit Message 格式

```
<type>: <简短英文标题，不超过 70 字符>

- 中文要点 1
- 中文要点 2
- ...

英文摘要行 1（对应中文要点，用于非中文读者快速理解）
英文摘要行 2

Co-Authored-By: Claude <模型名> <noreply@anthropic.com>
```

### Type 类型

- `feat` — 新功能
- `fix` — Bug 修复
- `refactor` — 重构（不改变外部行为）
- `style` — 样式/UI 调整（不涉及逻辑）
- `chore` — 构建、依赖、配置等杂项
- `docs` — 文档更新

### 规则

- 标题行用**英文**，简洁概括本次改动的核心
- Body 部分先写**中文要点**（给自己看），再写**英文摘要**（给协作者 / GitHub 看）
- 一个 commit 聚焦一件事；如果 body 需要超过 8 个要点，考虑拆分 commit
- 不要在 commit message 里包含文件路径列表（git diff 已经有了）
- message 末尾必须空一行后附 `Co-Authored-By: Claude <模型名> <noreply@anthropic.com>`。
  **`<模型名>` 写当次实际执行这个 commit 的模型**（`Opus 5` / `Sonnet 5` / `Haiku 4.5` …），
  不写死某个版本——署名要对得上是谁干的活，换了模型就跟着换
