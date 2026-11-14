"""SAQ 临时账号清理任务。薄壳 —— 真正干活的是 services/demo/cleanup。"""

import logging

from saq.types import Context

from app.services.demo.cleanup import purge_expired_guests

logger = logging.getLogger(__name__)


async def purge_expired_guests_task(ctx: Context) -> None:
    count = await purge_expired_guests()
    if count:
        logger.info("🧹 清理过期临时账号 %d 个", count)
    else:
        logger.debug("没有过期临时账号可清")
