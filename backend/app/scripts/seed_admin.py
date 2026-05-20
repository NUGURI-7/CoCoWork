"""初始化内置管理员账号（幂等）。

运行：
    cd backend
    uv run python -m app.scripts.seed_admin

前提：已跑过 migrate（users 表存在）；ADMIN_PASSWORD 已配置（默认 020121）。
"""

import asyncio
import logging

from tortoise.exceptions import IntegrityError

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import get_password_hash
from app.db.postgresql import pg_client
from app.models.user_model import User

logger = logging.getLogger(__name__)


async def seed_admin() -> None:
    """创建内置管理员（幂等）。

    可在两个场景调用：
    - main.py lifespan：Tortoise 已由 RegisterTortoise 连接，直接调用即可
    - 独立脚本 `python -m app.scripts.seed_admin`：经下方 main() 自行 connect/close

    并发安全：多 worker 同时启动时，exists() 检查可能都通过，
    靠 IntegrityError 兜底让重复创建优雅跳过，避免某个 worker 启动失败。
    """
    if not settings.ADMIN_PASSWORD:
        logger.warning("ADMIN_PASSWORD 未设置，跳过 admin 初始化")
        return

    if await User.filter(username=settings.ADMIN_USERNAME).exists():
        logger.info("管理员 %s 已存在，跳过", settings.ADMIN_USERNAME)
        return

    try:
        await User.create(
            username=settings.ADMIN_USERNAME,
            email=settings.ADMIN_EMAIL,
            password_hash=get_password_hash(settings.ADMIN_PASSWORD),
            nick_name="管理员",
            is_admin=True,
        )
        logger.info("✅ 管理员 %s 创建成功", settings.ADMIN_USERNAME)
    except IntegrityError:
        logger.info("管理员 %s 已存在（并发创建），跳过", settings.ADMIN_USERNAME)


async def main() -> None:
    setup_logging()
    await pg_client.connect()
    try:
        await seed_admin()
    finally:
        await pg_client.close()


if __name__ == "__main__":
    asyncio.run(main())
