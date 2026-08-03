"""SAQ 存档清理任务。

薄壳 —— 真正干活的是 db/checkpointer.sweep()。那个模块本来就管着这几张表的
开池与建表，清理是同一件事的另一半，没有理由分家。

不重试（CronSpec 默认 retries=0）：它每天都来，这次没跑成明天照样清，而且要清
的东西一条没少。跟文档处理正相反 —— 那个丢了用户会永远卡在「处理中」。
"""

import logging

from saq.types import Context

from app.db.checkpointer import sweep

logger = logging.getLogger(__name__)


async def cleanup_checkpoints_task(ctx: Context) -> None:
    """清一遍过期存档。"""
    count = await sweep()
    if count:
        logger.info("🧹 清理过期图存档 %d 个", count)
    else:
        # 平时大多是这个分支（没积压就没得清），按 INFO 打是刷屏
        logger.debug("没有过期图存档可清")
