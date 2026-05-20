import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.http import register_middlewares
from app.core.logging import setup_logging
from app.core.redis import RedisClient
from app.db.postgresql import TORTOISE_CONFIG

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(app, config=TORTOISE_CONFIG):
        redis_conn = RedisClient()
        await redis_conn.connect()
        app.state.redis = redis_conn
        logger.info("🚀 %s v%s 启动完成", settings.APP_NAME, settings.APP_VERSION)
        try:
            yield
        finally:
            await redis_conn.close()
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        access_log=False,
    )
