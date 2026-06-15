from typing import Any


class AppApiException(Exception):
    """业务异常基类。

    所有由业务逻辑主动抛出的异常都应继承此类。被 app_exception_handler
    捕获后会包装成统一响应壳 `{code, message, data}`。
    """

    def __init__(self, code: int = 500, message: str = "Service error", data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(self.message)


class NotFound404(AppApiException):
    def __init__(self, message: str = "资源不存在", code: int = 404, data: Any = None):
        super().__init__(code=code, message=message, data=data)


class AppAuthenticationFailed(AppApiException):
    """401 未登录 / token 失效"""

    def __init__(self, message: str = "未登录或登录已过期", code: int = 401, data: Any = None):
        super().__init__(code=code, message=message, data=data)


class AppUnauthorizedFailed(AppApiException):
    """403 已登录但权限不足"""

    def __init__(self, message: str = "权限不足", code: int = 403, data: Any = None):
        super().__init__(code=code, message=message, data=data)


class ValidationException(AppApiException):
    """400 业务侧参数校验失败（与 FastAPI 框架级 RequestValidationError 区分）"""

    def __init__(self, message: str = "参数验证失败", code: int = 400, data: Any = None):
        super().__init__(code=code, message=message, data=data)

class Conflict409(AppApiException):
    """409 资源冲突（如唯一约束撞库：重复招募同一 agent）"""

    def __init__(self, message: str = "资源冲突", code: int = 409, data: Any = None):
        super().__init__(code=code, message=message, data=data)