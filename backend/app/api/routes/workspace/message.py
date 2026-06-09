from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.workspace import MessageOut
from app.services.workspace import MessageService, get_message_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
    tags=["messages"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]


@router.get("", summary="列出 conversation 下的消息历史")
async def list_messages(
    workspace_id: UUID,
    conversation_id: UUID,
    current_user: CurrentUserDep,
    svc: MessageServiceDep,
) -> ResponseModel[list[MessageOut]]:
    messages = await svc.list_in_conversation(
        current_user, workspace_id, conversation_id,
    )
    return success(data=messages)