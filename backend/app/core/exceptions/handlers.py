import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.core.exceptions.types import AppApiException

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppApiException) -> JSONResponse:
    """业务异常：把 AppApiException 及子类翻译成统一响应壳。"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """框架级 HTTP 异常：路由不存在、依赖直接 raise HTTPException 等。"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求参数校验失败：取第一条错误拼成 `field:msg` 给前端展示。"""
    errors = exc.errors()
    if errors:
        first = errors[0]
        field = first.get("loc", ["unknown"])[-1]
        msg = first.get("msg", "parameter validate error")
        error_message = f"{field}:{msg}"
    else:
        error_message = "parameter validate error"

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 400,
            "message": error_message,
            "data": errors,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：未预料的异常。完整堆栈走日志，响应体只暴露脱敏文案。"""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """统一注册 4 个全局异常处理器。

    顺序无关（FastAPI 按异常类型精确匹配），但越具体越靠前便于阅读：
    业务异常 → 框架 HTTP 异常 → 校验异常 → 兜底 Exception。
    """
    app.add_exception_handler(AppApiException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
