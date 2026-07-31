from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.workspace import (
    ConversationCreate,
    ConversationOut,
    ConversationTitleIn,
    ConversationTitleOut,
    ConversationUpdate,
)
from app.services.workspace import ConversationService, get_conversation_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations",
    tags=["conversations"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]


@router.post("", summary="创建 Conversation")
async def create_conversation(
    workspace_id: UUID,
    data: ConversationCreate,
    current_user: CurrentUserDep,
    svc: ConversationServiceDep,
) -> ResponseModel[ConversationOut]:
    conv = await svc.create(current_user, workspace_id, data)
    return success(data=conv, message="创建成功")


@router.get("", summary="列出 workspace 下的对话")
async def list_conversations(
    workspace_id: UUID,
    current_user: CurrentUserDep,
    svc: ConversationServiceDep,
) -> ResponseModel[list[ConversationOut]]:
    convs = await svc.list_in_workspace(current_user, workspace_id)
    return success(data=convs)


@router.get("/{conversation_id}", summary="Conversation 详情")
async def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    current_user: CurrentUserDep,
    svc: ConversationServiceDep,
) -> ResponseModel[ConversationOut]:
    conv = await svc.get_by_id(current_user, workspace_id, conversation_id)
    return success(data=conv)


@router.put("/{conversation_id}", summary="更新 Conversation")
async def update_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    data: ConversationUpdate,
    current_user: CurrentUserDep,
    svc: ConversationServiceDep,
) -> ResponseModel[ConversationOut]:
    conv = await svc.update(current_user, workspace_id, conversation_id, data)
    return success(data=conv, message="更新成功")


@router.post("/{conversation_id}/generate-title", summary="自动生成对话标题")
async def generate_conversation_title(
    workspace_id: UUID,
    conversation_id: UUID,
    data: ConversationTitleIn,
    current_user: CurrentUserDep,
    svc: ConversationServiceDep,
) -> ResponseModel[ConversationTitleOut]:
    title = await svc.generate_title(
        current_user, workspace_id, conversation_id, data.content,
    )
    return success(data=ConversationTitleOut(title=title))


@router.delete("/{conversation_id}", summary="删除 Conversation")
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    current_user: CurrentUserDep,
    svc: ConversationServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, workspace_id, conversation_id)
    return success(message="删除成功")