import logging
import time

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from uuid_utils import uuid4

from app.core.config import settings
from app.core.request_context import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class ConditionalGZipMiddleware:
    """条件 GZip 压缩 —— 匹配 exclude_prefixes 的路径直接放行。

    设计：
    - 静态资源（/assets, index.html）压缩，主战场，JS/CSS 1MB 级别能压到 1/3
    - API 路径全部排除：
        * SSE（text/event-stream）被 buffer 会破坏流式实时性 → 必跳
        * 其他 JSON 接口压缩收益不大（响应通常 < 10K），统一跳过更简洁
    - 未来加新 SSE 接口零改动，不需要再维护路径白名单
    """

    def __init__(
            self,
            app: ASGIApp,
            exclude_prefixes: tuple[str, ...] = (),
            minimum_size: int = 500,
            compresslevel: int = 6,
    ):
        self._raw_app = app
        self._gzip_app = GZipMiddleware(
            app, minimum_size=minimum_size, compresslevel=compresslevel
        )
        self._exclude = exclude_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if any(path.startswith(p) for p in self._exclude):
                await self._raw_app(scope, receive, send)
                return
        await self._gzip_app(scope, receive, send)


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


class AccessLogMiddleware:
    """请求日志：方法、路径、状态码、耗时、来源 IP（纯 ASGI 实现）。

    替代 uvicorn 默认 access log（main.py 关了 `access_log=False`），
    与 RequestID 协同时日志会自动带上 [req-xxx] 前缀（由 logger formatter 注入）。

    用纯 ASGI 而非 BaseHTTPMiddleware：后者会把下游响应包进 anyio task group
    + 内存管道转交，客户端断连时整组任务被强杀，下游 generator 的 finally
    跑不到 —— SSE 场景下 stream 端点 finally 里的落库会被吞掉，
    必须等进程退出 uvicorn 统一清算 async generator 时才执行（= 长跑服务永不落库）。
    纯 ASGI 形态只透传 scope/receive/send，不切断下游生命周期。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope["method"]
        path = scope["path"]
        client = scope.get("client")
        ip = client[0] if client else "unknown"

        # status 通过 send wrapper 截 http.response.start 拿；
        # 下游连 start 都没发就异常时保持 0 表示"未发出响应"，比假装 500 诚实。
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %d %.1fms from %s",
                method, path, status_holder["status"], duration_ms, ip,
            )


def register_middlewares(app: FastAPI) -> None:
    """注册顺序：后注册的在外层。

    外 → 内 实际请求穿透顺序：RequestID → CORS → AccessLog → GZip → 路由。
    RequestID 必须最外层，否则 AccessLog 日志和路由内代码都拿不到 request_id。
    GZip 放最内层（紧贴路由）：response body 先压缩再向外冒泡，
    AccessLog / CORS / RequestID 只动 header 不读 body，互不干扰。
    """
    app.add_middleware(
        ConditionalGZipMiddleware,
        exclude_prefixes=(settings.API_PREFIX,),  # /api/v1 整个排除（含 SSE）
        minimum_size=500,
        compresslevel=6,
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
