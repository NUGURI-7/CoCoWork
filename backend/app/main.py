import logging
from contextlib import asynccontextmanager

from pathlib import Path

import jieba
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.http import register_middlewares
from app.core.logging import setup_logging
from app.core.redis import RedisClient
from app.db.postgresql import TORTOISE_CONFIG
from app.scripts.seed_admin import seed_admin
from app.services.skill.builtin import load_builtin_skills
from app.tasks.queue import queue as task_queue
from app.core.observability import init_langfuse, shutdown_langfuse
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(app, config=TORTOISE_CONFIG):
        redis_conn = RedisClient()
        await redis_conn.connect()
        app.state.redis = redis_conn
        await seed_admin()
        load_builtin_skills()  # 同步函数，扫盘 + 校验，不合规直接抛
        langfuse_on = init_langfuse()
        jieba.initialize()  # 预热分词词典（~1s），开门前付掉，别让首个检索请求付
        logger.info(
            "🚀 %s v%s 启动完成 (Langfuse: %s)",
            settings.APP_NAME, settings.APP_VERSION,
            "on" if langfuse_on else "off",
        )
        try:
            yield
        finally:
            await task_queue.disconnect()  # 队列自持一条 Redis 连接，与上面的 RedisClient 各自独立
            await redis_conn.close()
            shutdown_langfuse()
    logger.info("👋 应用已停止")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG_MODE,
    lifespan=lifespan,
)

register_middlewares(app)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_PREFIX)

# ── 前端静态资源（生产环境：frontend/dist 存在时挂载；开发环境自动跳过）──────
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )


    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    # 转调 cli.dev()：IDE 直接跑 main.py 和终端 `uv run dev` 走同一个函数，
    # 启动配置只有一处，不会漂移
    from app.cli import dev

    dev()
