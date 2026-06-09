"""Message 请求/响应 schema。

Message 不开标准 REST POST/PUT/DELETE:
- 写消息走对话流端点(SSE), 不是 REST POST
- 编辑 / 删消息 v1 不做

只暴露:
- MessageOut: 列消息历史 / 流式落库后回前端
- MessageAppend: service 层内部 DTO(stream handler 流完后调 append),不是 API 契约
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import MessageRole, MessageStatus, SenderKind


class MessageOut(BaseModel):
    """message 对外输出(列表 + 流完落库返回)。"""

    id: UUID
    conversation_id: UUID
    role: MessageRole
    sender_kind: SenderKind
    sender_member_id: UUID | None
    content: list[dict[str, Any]]
    mentioned_member_ids: list[UUID]
    status: MessageStatus
    error_message: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageAppend(BaseModel):
    """service 层内部 DTO:stream handler 流完一条消息后调 service.append() 用。

    不是 API 契约,前端不直接发这个;由 stream 端点的 runner 收口拼出来传进来。
    """

    role: MessageRole
    sender_kind: SenderKind
    sender_member_id: UUID | None = None
    content: list[dict[str, Any]]
    mentioned_member_ids: list[UUID] = []
    status: MessageStatus = MessageStatus.DONE
    error_message: str = ""