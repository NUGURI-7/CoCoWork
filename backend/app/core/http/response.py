from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一响应壳，用于路由的 `response_model` 与 OpenAPI 文档生成。"""

    code: int = 200
    message: str = "success"
    data: T | None = None


class PageData(BaseModel, Generic[T]):
    """分页数据 payload，外层仍套 ResponseModel。"""

    total: int
    records: list[T]
    current_page: int
    page_size: int


def success(data: Any = None, message: str = "success") -> ResponseModel:
    """成功响应：返回 ResponseModel 实例。

    路由配合 `-> ResponseModel[XxxOut]` 返回类型，让 FastAPI 走 Pydantic
    Rust 序列化路径（比 jsonable_encoder 快）+ 自动过滤敏感字段 + 完整 swagger 文档。
    """
    return ResponseModel(message=message, data=data)


def page(
    total: int,
    records: list,
    current_page: int = 1,
    page_size: int = 10,
) -> ResponseModel[PageData]:
    """分页响应：data 字段为 PageData 实例。"""
    return ResponseModel(
        data=PageData(
            total=total,
            records=records,
            current_page=current_page,
            page_size=page_size,
        ),
    )
