import logging
import time

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """请求日志：方法、路径、状态码、耗时、来源 IP。

    替代 uvicorn 默认 access log（main.py 关了 `access_log=False`），
    以便统一日志格式、未来接日志收集系统。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        ip = request.client.host if request.client else "unknown"
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d %.1fms from %s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            ip,
        )
        return response


def register_middlewares(app: FastAPI) -> None:
    """中间件注册顺序自上而下 = 请求处理顺序（响应顺序反过来）。

    CORS 必须放在最外层（最先添加 = 最后执行）才能正确处理跨域预检 OPTIONS。
    """
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
