"""异常子包：业务异常类型 + FastAPI 处理器注册。"""

from app.core.exceptions.handlers import register_exception_handlers
from app.core.exceptions.types import (
    AppApiException,
    AppAuthenticationFailed,
    AppUnauthorizedFailed,
    Conflict409,
    NotFound404,
    ValidationException,
)

__all__ = [
    "AppApiException",
    "AppAuthenticationFailed",
    "AppUnauthorizedFailed",
    "NotFound404",
    "ValidationException",
    "register_exception_handlers",
    "Conflict409",
]
