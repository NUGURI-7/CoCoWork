"""请求级上下文：跨函数 / 跨异步任务安全地传递 request_id 等元信息。

使用 contextvars 而非 threading.local，因为 FastAPI 是异步框架，
每个请求都在独立的 asyncio Task 中执行，contextvars 会随 Task 拷贝。
"""

from contextvars import ContextVar

# 默认值用 "-"：遵循 Apache/Nginx access log 约定，表示"无值"
# 在 lifespan 启动日志、CLI 脚本等非 HTTP 上下文中可见
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """读取当前请求的 ID（无请求上下文时返回 '-'）。"""
    return request_id_var.get()


def set_request_id(value: str) -> None:
    """供中间件 / 测试 fixture 设置当前请求 ID。"""
    request_id_var.set(value)
