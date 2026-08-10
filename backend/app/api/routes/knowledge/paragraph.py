"""知识库文档分段：只读列表路由。

URL nested 在文档下：`/knowledge-bases/{kb_id}/documents/{doc_id}/paragraphs/...`。
段由处理管线产出，此处只提供查询——增删改随「分段编辑」一并做。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import PageData, PaginationDep, ResponseModel, success
from app.models.user import User
from app.schemas.knowledge import ParagraphOut
from app.services.knowledge import ParagraphService, get_paragraph_service

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/documents/{doc_id}/paragraphs",
    tags=["paragraphs"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
ParagraphServiceDep = Annotated[ParagraphService, Depends(get_paragraph_service)]


@router.get("/page", summary="分页列出文档的分段")
async def list_paragraphs_paginated(
        kb_id: UUID,
        doc_id: UUID,
        current_user: CurrentUserDep,
        svc: ParagraphServiceDep,
        params: PaginationDep,
) -> ResponseModel[PageData[ParagraphOut]]:
    """按 position 升序返回该文档的段，每段附子块数。"""
    return success(data=await svc.list_page(current_user, kb_id, doc_id, params))
