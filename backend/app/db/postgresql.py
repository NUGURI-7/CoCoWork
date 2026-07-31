import logging

from tortoise import Tortoise

from app.core.config import settings

logger = logging.getLogger(__name__)


# Tortoise ORM 配置字典
TORTOISE_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": settings.PG_HOST,
                "port": settings.PG_PORT,
                "user": settings.PG_USER,
                "password": settings.PG_PASSWORD,
                "database": settings.PG_DATABASE,
                "minsize": settings.PG_POOL_MIN_SIZE,
                "maxsize": settings.PG_POOL_MAX_SIZE,
            },
        },
    },
    "apps": {
        "models": {
            # D1 起在 app/models/ 下加业务模型文件，Tortoise 会自动发现
            "models": ["app.models"],
            "default_connection": "default",
            "migrations": "migrations",
        },
    },
    # aware UTC 收口。use_tz=False 时 auto_now 取的是「进程当时的墙上时钟」——
    # 换个 TZ 起服务写进去的就是错的时刻；且序列化出去不带时区标记，
    # 浏览器 new Date() 按本地时间解析，相对时间全乱。
    "use_tz": True,
    "timezone": "UTC",
}


class PostgreSQLClient:
    """非 FastAPI 上下文（ARQ worker、CLI 脚本）下使用的 Tortoise 启停封装。

    FastAPI 主进程通过 `RegisterTortoise` 直接接管，不走这里。
    """

    def __init__(self):
        self._initialized: bool = False

    async def connect(self):
        if self._initialized:
            return
        try:
            await Tortoise.init(config=TORTOISE_CONFIG)
            self._initialized = True
            logger.info("✅ PostgreSQL 连接成功")
        except Exception:
            logger.exception("❌ PostgreSQL 连接失败")
            raise

    async def close(self):
        if self._initialized:
            await Tortoise.close_connections()
            self._initialized = False
            logger.info("👋 PostgreSQL 连接已关闭")

    @property
    def is_connected(self) -> bool:
        return self._initialized


pg_client = PostgreSQLClient()
