# syntax=docker/dockerfile:1.7

# ── Stage 1: Build frontend ──────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production image ────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# Install Python deps (cached layer)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# 把 tiktoken 的编码表烤进镜像（切块按 token 计数要用，见 splitter/sentence_impl.py）。
# 首次 get_encoding 会去 openaipublic（Azure 存储）下这个文件；不预下的话，容器每次
# 重建后的第一次切块都得联网，网络不通就是一次静默的文档处理失败。
# 夹在依赖层与源码 COPY 之间：改后端代码不会让这层失效，重新构建不会重下。
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# Copy backend source
COPY backend/ ./

# 源码进来后再同步一次，这次装的是**项目自身**。
# 上面那次 sync 跑在 COPY 之前（为了让依赖层能被缓存），那时 app/ 还不存在，
# 所以 uv 只装了第三方依赖、没装本项目 —— venv 里没有 app 包。
# uvicorn 察觉不到这点（它会把 cwd 塞进 sys.path，而 WORKDIR 正好是源码根），
# 但 worker / sandboxd 走的是 .venv/bin 下的控制台脚本，Python 只把脚本所在目录
# 加进 sys.path、不加 cwd，于是 `from app.cli import worker` 直接 ModuleNotFoundError。
RUN uv sync --frozen --no-dev

# Copy built frontend from stage 1
COPY --from=frontend-builder /build/dist /app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
