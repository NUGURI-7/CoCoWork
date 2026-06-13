"""分页参数依赖。

offset 分页用 PaginationParams，由 FastAPI 从查询字符串自动注入。
未来加 keyset/cursor 时在本文件新增 CursorPaginationParams 即可。
"""
import asyncio
from typing import Annotated, TypeVar
from tortoise.queryset import QuerySet
from fastapi import Depends, Query
from pydantic import BaseModel, computed_field

from app.core.http.response import PageData

ModelT = TypeVar("ModelT")
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class PaginationParams(BaseModel):
    """offset 分页参数。

    - page: 1-based 页码（页码从 1 开始，不是 0）
    - page_size: 每页数量，硬上限 100，防 ?page_size=999999 攻击
    """

    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量，1-100")] = 20

    @computed_field
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @computed_field
    @property
    def limit(self) -> int:
        return self.page_size


async def paginate(
        queryset: QuerySet[ModelT],
        params: PaginationParams,
        *,
        out: type[SchemaT],
) -> PageData[SchemaT]:
    """把 QuerySet 按分页参数切片 + 转 schema，吐 PageData。

    用法：
        qs = Document.filter(kb_id=kb_id).order_by("-created_at")
        return success(data=await paginate(qs, params, out=DocumentOut))
    """
    total, rows = await asyncio.gather(
        queryset.count(),
        queryset.offset(params.offset).limit(params.limit)
    )

    return PageData(
        total=total,
        records=[out.model_validate(r) for r in rows],
        current_page=params.page,
        page_size=params.page_size,
    )


PaginationDep = Annotated[PaginationParams, Depends()]
