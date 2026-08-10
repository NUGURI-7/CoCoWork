"""Paragraph（文档分段）只读 service。

段是处理管线的产物，不在这里创建 / 修改——本 service 只管「按文档列出段」
这一件事。URL nested → 方法签名固定 (user, kb_id, doc_id, ...)。
可见性同文档：只能看自己创建的 KB 下的段。
"""

from uuid import UUID

from tortoise.functions import Count

from app.core.http import PageData, PaginationParams, paginate
from app.models.knowledge import Embedding, Paragraph, SourceType
from app.models.user import User
from app.schemas.knowledge import ParagraphOut


class ParagraphService:
    """分段只读查询。"""

    async def list_page(
            self, user: User, kb_id: UUID, doc_id: UUID, params: PaginationParams,
    ) -> PageData[ParagraphOut]:
        """分页列出文档下的段（按 position 升序），并回填每段的子块数。

        归属压进 JOIN：非本人的库、或 doc 不属于这个 kb → 空结果而非 404。
        文档存不存在由前端那边的 `GET /documents/{doc_id}` 负责报，这里不重复
        判断，也不泄漏「库/文档是否存在」。
        """
        qs = Paragraph.filter(
            document_id=doc_id,
            knowledge_base_id=kb_id,
            knowledge_base__created_by=user,
        ).order_by("position")

        page_data = await paginate(qs, params, out=ParagraphOut)
        await self._fill_chunk_counts(page_data.records)
        return page_data

    @staticmethod
    async def _fill_chunk_counts(records: list[ParagraphOut]) -> None:
        """给本页的段补上子块数：一次聚合查询搞定，不做 N+1。

        刻意不用 `annotate` 挂在主查询上——那会让分页 queryset 带上 GROUP BY，
        `paginate` 里的 `count()` 就不再是「有多少段」而是「有多少组」。
        分页归分页、聚合归聚合，两条查询各自正确。

        只数 content 向量：`Document.chunk_count` 的口径就是它，question /
        title 那两类是多向量留的口子，不算「这段切了几块」。
        """
        if not records:
            return

        rows = await (
            Embedding.filter(
                paragraph_id__in=[r.id for r in records],
                source_type=SourceType.CONTENT,
            )
            .annotate(cnt=Count("id"))
            .group_by("paragraph_id")
            .values("paragraph_id", "cnt")
        )
        counts = {row["paragraph_id"]: row["cnt"] for row in rows}
        for record in records:
            record.chunk_count = counts.get(record.id, 0)


async def get_paragraph_service() -> ParagraphService:
    return ParagraphService()
