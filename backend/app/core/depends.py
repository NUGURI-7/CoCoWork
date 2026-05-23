"""FastAPI 依赖注入工具。

本文件**只放认证 / 上下文相关**的依赖。业务 service 的 provider
（如 `get_user_service`）请放各 service 模块自己附近，避免本文件膨胀。
"""

from typing import Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions.types import AppAuthenticationFailed, AppUnauthorizedFailed
from app.core.security import verify_token
from app.models.user import User
from app.services.user import UserService, get_user_service

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


async def get_current_user(
    payload: dict[str, Any] = Depends(get_current_token_payload),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """从 JWT payload 加载真实 User 实体。

    基于 `get_current_token_payload` 二次组合：底层依赖只解 token，
    本依赖额外做 DB 查询 + 账户状态检查。

    每次请求都重新查 DB + 检查 is_active，确保用户被禁用后即刻失效
    （而非等 token 过期）。
    """
    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise AppAuthenticationFailed("token 缺少 sub 声明")

    try:
        user_id = UUID(user_id_raw)
    except (ValueError, TypeError) as e:
        raise AppAuthenticationFailed("token sub 格式非法") from e

    user = await user_service.get_user_by_id(user_id)
    if user is None:
        raise AppAuthenticationFailed("用户不存在")
    if not user.is_active:
        raise AppAuthenticationFailed("账户已被禁用")

    return user


async def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """管理员守卫：基于 get_current_user 二次校验 is_admin。"""
    if not user.is_admin:
        raise AppUnauthorizedFailed("需要管理员权限")
    return user
