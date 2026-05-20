import logging
import time

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from uuid_utils import uuid4

from app.core.request_context import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """请求 ID 中间件（纯 ASGI 实现）。

    - 入口：从 X-Request-ID header 透传上游 ID，没有则生成 12 位短 UUID。
    - 上下文：写入 request_id_var，供 logger filter / 业务代码读取。
    - 出口：把 request_id 回写到响应 header，便于客户端 / 网关侧关联。

    用纯 ASGI 接口而非 BaseHTTPMiddleware：后者在嵌套 Task 中传递 contextvar
    历史上有兼容性问题，纯 ASGI 形态最稳。
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break

        request_id = incoming or uuid4().hex[:12]
        token = request_id_var.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """请求日志：方法、路径、状态码、耗时、来源 IP。

    替代 uvicorn 默认 access log（main.py 关了 `access_log=False`），
    与 RequestID 协同时日志会自动带上 [req-xxx] 前缀（由 logger formatter 注入）。
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
    """注册顺序：后注册的在外层。

    外 → 内 实际请求穿透顺序：RequestID → CORS → AccessLog → 路由。
    RequestID 必须最外层，否则 AccessLog 日志和路由内代码都拿不到 request_id。
    """
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
