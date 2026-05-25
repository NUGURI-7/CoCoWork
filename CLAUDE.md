## Global User Preferences

1. Prefer production-grade, industry-standard solutions over quick fixes or ad hoc hacks. When a widely accepted standard approach exists, use it instead of inventing a custom workaround.
2. 所有任务动手前都需要先描述步骤/方案，等用户审批后再编写代码。对于架构设计、模块搭建、技术选型等复杂任务，代码方案需额外经过一轮审批后才能写入文件。
3. If the user's request is ambiguous or missing key details, ask clarifying questions before writing code.
4. **每次开始新对话时，必须先读取 `../CODING-STYLE.md`（Amoy 根目录），这是项目编码规范，严格遵循其中的代码风格、架构模式和设计思维。如果你是 Claude 模型则不用读（这些规范本来就是你写的）。**
5. 每次开始新任务时，如果存在 `docs/context.md`，先读取它。
6. 每次完成有意义的项目改动后，更新 `docs/context.md`，同步最新的当前状态。
7. 保持 `docs/context.md` 精简：优先重写摘要，只保留最近迭代，并将更早内容压缩进历史摘要。

# CoCoWork — Claude Code 指南

> **AI Agent 管理平台**（暂定方向，随开发推进持续演化）：基于 LangGraph + FastAPI + PostgreSQL（pgvector）+ Redis 构建后端，React 19 + shadcn/ui 构建前端。核心能力包括：多 Agent 编排与调度、RAG 混合检索（向量 + 全文检索 + 重排序）、Prompt 版本管理、Skill 技能市场、知识库管理；支持语音交互（ASR/TTS）与视觉理解多模态输入输出；提供多层 RBAC 权限管控与资源隔离。定位为可管理、可编排、可扩展的一站式 Agent 平台。

## 项目结构

```
CoCoWork/
├── backend/                  # FastAPI + Tortoise ORM + PostgreSQL + Redis + LangGraph + ARQ
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
│   │   └── tasks/            # ARQ 异步任务
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

## Git 提交规范

### Commit Message 格式

```
<type>: <简短英文标题，不超过 70 字符>

- 中文要点 1
- 中文要点 2
- ...

英文摘要行 1（对应中文要点，用于非中文读者快速理解）
英文摘要行 2

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
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
- message 末尾必须空一行后附 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
