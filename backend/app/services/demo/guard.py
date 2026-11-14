"""临时账号的写操作白名单：默认拒绝，只放行体验对话需要的接口。"""

from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.depends import bearer_scheme
from app.core.exceptions import AppAuthenticationFailed, AppUnauthorizedFailed
from app.core.security import verify_token
from app.models.user import User

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_CONVERSATION_WRITES = (
    "/conversations/{conversation_id}",
    "/conversations/{conversation_id}/generate-title",
    "/conversations/{conversation_id}/stream",
    "/conversations/{conversation_id}/messages/{message_id}/resume",
)

GUEST_WRITABLE_ROUTES = frozenset(
    {
        f"{settings.API_PREFIX}/demo/guest-session",
        *(f"{settings.API_PREFIX}/agents/{{agent_id}}{p}" for p in _CONVERSATION_WRITES),
        *(f"{settings.API_PREFIX}/workspaces/{{workspace_id}}{p}" for p in _CONVERSATION_WRITES),
    }
)


async def guest_write_guard(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if not settings.DEMO_ENABLED or request.method in READ_METHODS or credentials is None:
        return
    if request.scope["route"].path in GUEST_WRITABLE_ROUTES:
        return
    try:
        user_id = UUID(verify_token(credentials.credentials).get("sub", ""))
    except (AppAuthenticationFailed, ValueError):
        return
    is_guest = await User.filter(id=user_id).first().values_list("is_guest", flat=True)
    if is_guest:
        raise AppUnauthorizedFailed("体验账号不支持此操作")
