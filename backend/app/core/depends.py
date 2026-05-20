"""FastAPI 依赖注入工具。

本文件**只放认证 / 上下文相关**的依赖。业务 service 的 provider
（如 `get_user_service`）请放各 service 模块自己附近，避免本文件膨胀。
"""

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions.types import AppAuthenticationFailed
from app.core.security import verify_token

# auto_error=False：缺失 Authorization header 时不让 FastAPI 自己抛 403，
# 我们要自己抛 AppAuthenticationFailed 走统一异常响应。
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """从 Authorization: Bearer xxx 中解出 JWT payload。

    不查数据库，只做 token 解码与有效性校验。需要拿到 User 实体的场景，
    D1 阶段会在本文件追加 `get_current_user` 依赖，基于本依赖二次组合。
    """
    if credentials is None:
        raise AppAuthenticationFailed("未提供认证 token")
    return verify_token(credentials.credentials)
