"""SAQ 文档处理任务。

worker 取到任务后调 `process_document` 跑完整条管线（解析 → 切段 → 切块 → 向量化），
出错时按剩余重试次数记状态：还有机会就把 stage 退回 queued 等下一轮，次数用尽才标
failed。中途不标 failed，前端轮询全程只看到 processing。

doc_id 经 Redis 传递，只能是 str，UUID 在此还原。
"""

import logging
from uuid import UUID

from saq.types import Context

from app.models.knowledge import Document, DocStage, DocStatus
from app.services.knowledge.document_processor import process_document

logger = logging.getLogger(__name__)


async def process_document_task(ctx: Context, *, doc_id: str) -> None:
    """跑文档处理管线，失败时按剩余重试次数决定退回重排还是标终态。"""
    document_id = UUID(doc_id)

    try:
        await process_document(document_id)
    except Exception as e:
        job = ctx["job"]

        if job.retryable:
            # 还有重试机会：stage 退回 queued，前端继续看到「处理中」
            logger.warning(
                "文档处理失败待重试 doc_id=%s (%d/%d): %s",
                document_id, job.attempts, job.retries, e,
            )
            await Document.filter(id=document_id).update(stage=DocStage.QUEUED)
        else:
        # 重试用尽：标 failed，stage 停在出错那步供排查
            logger.error(
                "文档处理失败已放弃 doc_id=%s (%d 次尝试): %s",
                document_id, job.attempts, e,
            )
            await Document.filter(id=document_id).update(
                status=DocStatus.FAILED,
                error_message=f"{type(e).__name__}: {e}",
            )
            # 重抛：不抛的话 SAQ 会把 job 记成 COMPLETE，队列侧的账是假的
        raise