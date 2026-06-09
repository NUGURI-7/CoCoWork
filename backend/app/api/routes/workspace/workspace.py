from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.services.workspace import WorkspaceService, get_workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]
WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.post("", summary="创建 Workspace")
async def create_workspace(
    data: WorkspaceCreate,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> ResponseModel[WorkspaceOut]:
    workspace = await svc.create(current_user, data)
    return success(data=workspace, message="创建成功")


@router.get("", summary="列出自己的 Workspace")
async def list_workspaces(
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> ResponseModel[list[WorkspaceOut]]:
    workspaces = await svc.list_own(current_user)
    return success(data=workspaces)


@router.get("/{workspace_id}", summary="Workspace 详情")
async def get_workspace(
    workspace_id: UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> ResponseModel[WorkspaceOut]:
    workspace = await svc.get_by_id(current_user, workspace_id)
    return success(data=workspace)


@router.put("/{workspace_id}", summary="更新 Workspace")
async def update_workspace(
    workspace_id: UUID,
    data: WorkspaceUpdate,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> ResponseModel[WorkspaceOut]:
    workspace = await svc.update(current_user, workspace_id, data)
    return success(data=workspace, message="更新成功")


@router.delete("/{workspace_id}", summary="删除 Workspace")
async def delete_workspace(
    workspace_id: UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, workspace_id)
    return success(message="删除成功")