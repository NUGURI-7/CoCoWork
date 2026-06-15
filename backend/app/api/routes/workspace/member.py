from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.workspace import MemberOut, MemberRecruitIn
from app.services.workspace import MemberService, get_member_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/members",
    tags=["workspace-members"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
MemberServiceDep = Annotated[MemberService, Depends(get_member_service)]

@router.post("", summary="招募成员")
async def recruit_member(
    workspace_id: UUID,
    data: MemberRecruitIn,
    current_user: CurrentUserDep,
    svc: MemberServiceDep,
) -> ResponseModel[MemberOut]:
    member = await svc.recruit(current_user, workspace_id, data)
    return success(data=member, message="招募成功")


@router.get("", summary="列出 workspace 成员")
async def list_members(
    workspace_id: UUID,
    current_user: CurrentUserDep,
    svc: MemberServiceDep,
) -> ResponseModel[list[MemberOut]]:
    members = await svc.list_in_workspace(current_user, workspace_id)
    return success(data=members)

@router.delete("/{member_id}", summary="移除成员")
async def remove_member(
    workspace_id: UUID,
    member_id: UUID,
    current_user: CurrentUserDep,
    svc: MemberServiceDep,
) -> ResponseModel[None]:
    await svc.remove(current_user, workspace_id, member_id)
    return success(message="移除成功")



