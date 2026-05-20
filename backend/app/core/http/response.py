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


def success(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def page(
    total: int,
    records: list,
    current_page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": total,
            "records": records,
            "current_page": current_page,
            "page_size": page_size,
        },
    }
