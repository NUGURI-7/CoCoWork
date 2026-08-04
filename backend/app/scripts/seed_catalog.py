"""把内置模型目录灌进库（幂等）。

运行：
    cd backend
    uv run python -m app.scripts.seed_catalog

前提：已跑过 migrate（provider_model_catalog 表存在）。
"""

import asyncio
import logging

from app.core.logging import setup_logging
from app.db.postgresql import pg_client
from app.models.model import ProviderModelCatalog
from app.scripts.catalog_data import CATALOG

logger = logging.getLogger(__name__)


async def seed_catalog() -> None:
    """按 CATALOG 清单补齐目录条目（幂等，只增不删）。

    只增不删是刻意的：这张表管理员可以在后台随手编辑，删掉的条目多半是
    「我不用这个」，种子没有立场把它塞回去……但也不打算记住这件事——
    真被重启带回来了，再删一次即可，代价低于为此加一张状态表。

    并发安全：多 worker 同时启动时 existing 检查可能都通过，
    靠 ignore_conflicts 让重复插入静默跳过（唯一键是 provider_type + model_id）。
    """
    existing = {
        (provider_type, model_id)
        for provider_type, model_id in await ProviderModelCatalog.all().values_list(
            "provider_type", "model_id",
        )
    }

    rows = [
        ProviderModelCatalog(
            provider_type=provider_type, model_id=model_id, model_type=model_type,
        )
        for provider_type, by_type in CATALOG.items()
        for model_type, model_ids in by_type.items()
        for model_id in model_ids
        if (provider_type, model_id) not in existing
    ]

    if not rows:
        logger.info("模型目录已齐备（%d 条），跳过", len(existing))
        return

    await ProviderModelCatalog.bulk_create(rows, ignore_conflicts=True)
    logger.info("✅ 模型目录补入 %d 条", len(rows))


async def main() -> None:
    setup_logging()
    await pg_client.connect()
    try:
        await seed_catalog()
    finally:
        await pg_client.close()


if __name__ == "__main__":
    asyncio.run(main())
