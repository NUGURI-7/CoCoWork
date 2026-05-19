from tortoise import Tortoise

from app.core.config import settings


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
    "use_tz": False,
    "timezone": "Asia/Shanghai",
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
            print("✅ PostgreSQL 连接成功")
        except Exception as e:
            print(f"❌ PostgreSQL 连接失败: {e}")
            raise

    async def close(self):
        if self._initialized:
            await Tortoise.close_connections()
            self._initialized = False
            print("👋 PostgreSQL 连接已关闭")

    @property
    def is_connected(self) -> bool:
        return self._initialized


pg_client = PostgreSQLClient()
