"""SAQ 记忆整理任务。

worker 取到之后调 MemoryDigestService 跑一次沉淀。**薄壳,刻意不做错误处理** ——
`run()` 内部已经把「模型抽风 / 输出不是 JSON / 管家没配模型」这类预期内的失败
都吞成了 False(记忆那条规矩是失败绝不落库),能漏到这一层的只剩数据库挂了
这种真意外,那种就该抛出去让 SAQ 如实记一笔失败,不该在这儿吞掉。

**不重试**(retries 在入队处给 0):整理每 N 轮自动来一次,这次没成下次自然
还会来,重试只是多烧一次模型调用。这跟文档处理正相反 —— 那个丢了用户会永远
卡在「处理中」,必须有人负责;这个丢了没人受损。

conversation_id 经 Redis 传递,只能是 str,UUID 在此还原。
"""

import logging
from uuid import UUID

from saq.types import Context

from app.services.memory import MemoryDigestService

logger = logging.getLogger(__name__)


async def digest_memory_task(ctx: Context, *, conversation_id: str) -> None:
    """跑一次记忆整理。写没写库由 service 判断,这里只记一笔。"""
    changed = await MemoryDigestService().run(UUID(conversation_id))
    if not changed:
        # 真沉淀出东西时 service 自己会打 INFO;这里只补「跑了但没产出」那一半,
        # 压到 debug —— 大部分轮次都没产出,按 INFO 打就是刷屏
        logger.debug("记忆整理没有产出 conversation_id=%s", conversation_id)
