from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.config import settings
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.demo import SceneEntryOut
from app.schemas.user import TokenOut, UserOut
from app.services.demo import GuestService, get_guest_service, resolve_scene

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
