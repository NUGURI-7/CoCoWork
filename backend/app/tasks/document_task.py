"""SAQ 文档处理任务：解析、建索引各一个，由用户分别触发。

worker 取到任务后调 document_processor 里对应的一步。出错时按剩余重试次数记状态：
还有机会就把 stage 退回 queued 等下一轮，次数用尽才标 failed —— stage 停在出错
那步，用户重试时据此决定重做哪一步。中途不标 failed，前端轮询全程只看到 processing。

doc_id 经 Redis 传递，只能是 str，UUID 在此还原。
"""

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from saq.types import Context

from app.models.knowledge import Document, DocStage, DocStatus
from app.services.knowledge.document_processor import index_document, parse_document

logger = logging.getLogger(__name__)


async def parse_document_task(ctx: Context, *, doc_id: str) -> None:
    """第一步：解析 → 存图 → 段落入库。"""
    await _run_step(ctx, parse_document, UUID(doc_id))


async def index_document_task(ctx: Context, *, doc_id: str) -> None:
    """第二步：段落 → 子块向量 + 关键词词条。"""
    await _run_step(ctx, index_document, UUID(doc_id))


async def _run_step(
        ctx: Context, step: Callable[[UUID], Awaitable[None]], document_id: UUID,
) -> None:
    """执行一步处理，失败时按剩余重试次数决定退回重排还是标终态。"""
    try:
        await step(document_id)
    except Exception as e:
        job = ctx["job"]

        if job.retryable:
            # 还有重试机会：stage 退回 queued，前端继续看到「处理中」
            logger.warning(
                "文档处理失败待重试 doc_id=%s step=%s (%d/%d): %s",
                document_id, step.__name__, job.attempts, job.retries, e,
            )
            await Document.filter(id=document_id).update(stage=DocStage.QUEUED)
        else:
            # 重试用尽：标 failed，stage 停在出错那步供排查和重试分流
            logger.error(
                "文档处理失败已放弃 doc_id=%s step=%s (%d 次尝试): %s",
                document_id, step.__name__, job.attempts, e,
            )
            await Document.filter(id=document_id).update(
                status=DocStatus.FAILED,
                error_message=f"{type(e).__name__}: {e}",
            )
        # 重抛：不抛的话 SAQ 会把 job 记成 COMPLETE，队列侧的账是假的
        raise
