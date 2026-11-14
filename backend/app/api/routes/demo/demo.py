from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from redis import asyncio as aioredis

from app.core.config import settings
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.core.http import ResponseModel, success
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.demo import SceneEntryOut, SceneQuotaOut
from app.schemas.user import TokenOut, UserOut
from app.services.demo import (
    GuestService,
    get_guest_service,
    remaining_scene_messages,
    resolve_scene,
)

router = APIRouter(prefix="/demo", tags=["demo"])

GuestServiceDep = Annotated[GuestService, Depends(get_guest_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_demo_enabled() -> None:
    if not settings.DEMO_ENABLED:
        raise NotFound404()


def client_ip(request: Request) -> str:
    return request.headers.get("cf-connecting-ip") or request.client.host


@router.post(
    "/guest-session",
    summary="创建体验访客会话",
    dependencies=[Depends(require_demo_enabled)],
)
async def create_guest_session(
    request: Request,
    guest_service: GuestServiceDep,
) -> ResponseModel[TokenOut]:
    result = await guest_service.sign_in(client_ip(request))
    return success(
        data=TokenOut(
            access_token=result["access_token"],
            user=UserOut.model_validate(result["user"]),
        )
    )


@router.get(
    "/scenes/{scene}/entry",
    summary="解析体验场景的目标页面",
    dependencies=[Depends(require_demo_enabled)],
)
async def get_scene_entry(scene: str, current_user: CurrentUserDep) -> ResponseModel[SceneEntryOut]:
    return success(data=await resolve_scene(current_user, scene))


@router.get(
    "/quota/{target_id}",
    summary="当前访客在这个场景今天还剩几次",
    dependencies=[Depends(require_demo_enabled)],
)
async def get_scene_quota(
    target_id: UUID,
    current_user: CurrentUserDep,
    redis: aioredis.Redis = Depends(get_redis),
) -> ResponseModel[SceneQuotaOut]:
    if not current_user.is_guest:
        return success(data=SceneQuotaOut(remaining=None, limit=None))
    remaining = await remaining_scene_messages(redis, current_user, str(target_id))
    return success(
        data=SceneQuotaOut(remaining=remaining, limit=settings.DEMO_MESSAGES_PER_SCENE_PER_DAY)
    )
