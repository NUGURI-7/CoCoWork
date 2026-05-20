import logging
from typing import Optional

from redis import asyncio as aioredis
from redis.asyncio import ConnectionPool
from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 异步客户端封装。

    - FastAPI 主进程：在 lifespan 里 new + connect，挂在 `app.state.redis`，
      路由通过 `Depends(get_redis)` 拿到底层 client。
    - 非 FastAPI 上下文（ARQ worker、CLI 脚本）：用模块底部的 `redis_client` 单例。
    """

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        self._pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
        self._client = aioredis.Redis(connection_pool=self._pool)
        try:
            await self._client.ping()
            logger.info("✅ Redis 连接成功")
        except Exception:
            logger.exception("❌ Redis 连接失败")
            raise

    async def close(self):
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("👋 Redis 连接已关闭")

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis 客户端未初始化，请先调用 connect()")
        return self._client


redis_client = RedisClient()


async def get_redis(request: Request) -> aioredis.Redis:
    """FastAPI 依赖：从 `app.state.redis` 取底层 redis 客户端。

    用法：
        from fastapi import Depends
        from redis import asyncio as aioredis
        from app.core.redis import get_redis

        @router.get("/ping")
        async def ping(r: aioredis.Redis = Depends(get_redis)):
            await r.set("k", "v")
    """
    return request.app.state.redis.client
