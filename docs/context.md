# CoCoWork Context

## 项目概述
- CoCoWork 是一个个人独立开发的 full-stack 项目，后端使用 FastAPI，前端使用 Vue 3。
- 当前定位：AI Agent 管理平台（暂定方向，随开发推进持续演化），核心能力包括多 Agent 编排与调度、RAG 混合检索、Prompt 版本管理、Skill 技能市场、知识库管理。
- 这个文件是后续 AI 新对话的单一项目上下文来源。

## 早期方向参考（低权重）
- 这部分只用于提供产品方向上的大致印象，帮助 AI 理解项目可能的长期演化方向。
- 这不是正式需求，不构成强约束，也不代表相关能力已经实现。
- 如果与当前代码现状、你在当次对话中的明确要求或后续决策冲突，应以实际项目状态和当前任务为准。
- 远期愿景：可管理、可编排、可扩展的一站式 Agent 平台，支持语音交互（ASR/TTS）与视觉理解多模态输入输出，提供多层 RBAC 权限管控与资源隔离。
- 当前阶段聚焦基础设施搭建和核心后端能力验证，前端仅做满足测试和验证需要的最小实现。

## 技术栈
- Backend: FastAPI, Tortoise ORM, PostgreSQL (pgvector 计划，本期未启用), Redis, LangGraph (未实装), ARQ (未实装)
- Frontend: Vue 3, Vite, TypeScript, Pinia, Vue Router, Tailwind CSS v4, shadcn-vue (Reka UI v2), `@phosphor-icons/vue` —— 本期未启动
- Python: 3.13.0（venv 在 `backend/.venv/`，由 uv 管理），Tortoise ORM 1.1.7 内置迁移（`tortoise` CLI 自动读 `pyproject.toml` 的 `[tool.tortoise]`，不引入 aerich）
- API prefix: `/api/v1`（写在 `settings.API_PREFIX`，main.py 通过 `app.include_router(api_router, prefix=settings.API_PREFIX)` 挂载）
- 数据库：复用 DaisyWind 同一个远端 PG 容器，仅 `PG_DATABASE` 不同（本项目 = `cocowork`）

## 当前已有功能
- 后端骨架可启动：`uv run python -m app.main` 跑通 lifespan，FastAPI 接 Tortoise + Redis，中间件 + 异常 + 日志全链路就绪。
- 仍**无业务路由 / 无 model**（app/models 是空包），数据库内无表 —— D1 阶段开始填充。
- 生产级日志系统就位：colorlog 开发模式 / JSON 生产模式（按 DEBUG_MODE 切），每条日志带 `[req-xxx]`。
- 认证薄层就位：JWT 编/解码 + argon2/bcrypt 密码哈希；`get_current_token_payload` 依赖可用，`get_current_user` 等 D1。

## 下一步
- **进入 Phase 3（D1 User 业务全栈）**：app/models/user_model.py + app/schemas/user_schema.py + app/services/user_service.py + app/api/routes/user.py。
- 同步在 depends.py 追加 `get_current_user`（基于 `get_current_token_payload` 二次组合 + Tortoise 查询 User 实体）。
- main.py 把 user 路由挂到 api_router。
- Phase 4（首次迁移）：`tortoise init` 初始化 migrations 目录，`makemigrations -n init_user`，`migrate` 应用到远端 PG 的 `cocowork` 库。
- 之后：Phase 5–7 前端 + Phase 4+ 真生产用的功能（Email 校验、限流、密码重置等）按需开。

## 开发注意事项
- 项目 UI 统一使用 `@phosphor-icons/vue`，不要引入手写 SVG 或第二套 icon library。
- 这个 context 文件应该保持紧凑，服务于 AI 快速读取，而不是承担完整项目历史归档。

## 维护规则
- 这个文件只保留当前仍然有效的项目状态。
- 更新时优先重写摘要，不要机械地无限追加内容。
- `最近迭代` 只保留最近 8 次以内的记录。
- 旧的迭代信息应压缩进 `历史摘要`，不要让全文持续变长。
- 如果某次改动不足以影响项目理解，就不要把噪音写进来。

## 最近迭代

### 2026-05-20 — Phase 2 后端通用模块全部完成（B2–B7 + 日志系统）
- B2 Redis 客户端 + lifespan 接入。
- B3 异常体系：5 个业务异常类 + 4 个 handler，统一 `{code, message, data}` 响应壳（沿用 DaisyWind "全 200" 风格）。
- B4 中间件：AccessLog + CORS；后续日志任务追加了 RequestIDMiddleware（纯 ASGI 实现规避 contextvar 跨 Task 丢失）。
- B5 统一响应壳：ResponseModel[T] / PageData[T] + success/page 函数；删掉了 DaisyWind 的 `error()` 反模式。
- B6 安全：argon2 主推 + bcrypt 兼容，`verify_token` 失败抛 `AppAuthenticationFailed`（不再返回 None），token 加 `iat` claim。
- B7 认证依赖薄层：`bearer_scheme` + `get_current_token_payload`；User 实体加载 (`get_current_user`) 推迟到 D1 完成 User 模型后再加。
- 中途插入：生产级日志系统（colorlog + python-json-logger，按 `DEBUG_MODE` 切换文本/JSON，RequestIDFilter 把 request_id 注入每条日志，接管 uvicorn 三个 logger，压低 9 个第三方库到 WARNING）。
- 中途插入：`app/core/` 重组成子包（`exceptions/`、`http/`、`logging/`），避免 11 文件平铺。
- 决策：分页字段沿用 DaisyWind 中式命名（records / current_page）；HTTP 状态码策略沿用 DaisyWind "全 200" 风格（与生产级 REST 偏好不同，按用户决策保留）。

### 2026-05-19 — Phase 1 后端骨架完成
- 决策：
  - 本轮范围 A+B+C+D1（骨架 + 后端通用 + 前端通用 + User 全栈），本次提交完成 A。
  - Agent 框架锁定 LangGraph，不从 DaisyWind 拷 `pydantic-ai` / `agents/` / `tools/` / `ingestion/`。
  - 复用 DaisyWind 远端 PG 容器，新建 database `cocowork`。
  - 迁移工具：Tortoise 1.x 内置（不引入 aerich，DaisyWind 那个 `aerich.ini` 是历史残留）。
  - Python 3.13 路线（容忍未来 Docker 也用 3.13）。
  - API 前缀 `/api/v1`，路由组单层（不像 DaisyWind 套两层）。
  - 测试基础设施先建（pytest 配置已就位）但 `conftest.py` 推迟到 D1 写 User 时连同第一个测试一起写，避免空 fixture 死代码。
- 落盘：
  - `backend/pyproject.toml`、`backend/.env.example`、`backend/app/{__init__,main}.py`、
    `backend/app/{api,core,db,models}/__init__.py`、`backend/app/core/config.py`、
    `backend/app/db/postgresql.py`、`backend/app/api/__init__.py`、
    `backend/migrations/README.md`、`backend/tests/__init__.py`。
  - 顶层 `.gitignore` 加了 `.DS_Store`。
- 与原 Phase 1 spec 的偏差：
  - `main.py` 暂未接 Redis / 异常处理器 / 中间件（依赖 B2/B3/B4 模块未到位），Phase 2 写完对应模块后回头补 4–6 行 import + register。
  - `pyproject.toml` 比最初规划多加了 `boto3` + `tavily-python`（用户确认后续会用）。但 `.env.example` 与 `config.py` 暂不放 R2 / Tavily 字段，等 E 阶段实装时再加，避免配置-代码不同步。
- 跑通验证：服务在 `127.0.0.1:7999`（或 .env 配的端口）成功启动，Tortoise 初始化无错。

## 历史摘要
（暂无）

## 后续使用方式
- 每次开启新的 AI 对话时，先读取这个文件。
- 每次完成有意义的开发后，更新这个文件一次。
- 可以直接用类似 `更新 context`、`把这次改动写入 context`、`压缩 context` 的指令触发维护。
