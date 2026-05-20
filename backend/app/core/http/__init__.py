"""HTTP 集成子包：FastAPI 中间件、统一响应壳等。"""

from app.core.http.middlewares import register_middlewares

__all__ = ["register_middlewares"]
