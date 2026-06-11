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

import uuid_utils.compat as uuid_compat
from pydantic import BaseModel, ConfigDict, Field

from app.models import MessageRole, MessageStatus, SenderKind
from app.schemas.agent.chat_schema import ContentBlock


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

class ConversationStreamIn(BaseModel):
    """workspace 对话流端点的请求 body。

    与 Playground 的 ChatStreamRequest 关键差异:**没有 history 字段**——
    workspace 对话历史的真源在 DB(messages 表),由后端拉取拼装;
    前端只送当前这一句。谁持有历史在请求契约上钉死,
    防止前后端各持一份互相漂移。
    """

    content: list[ContentBlock]


class MessageAppend(BaseModel):
    """service 层内部 DTO:stream handler 流完一条消息后调 service.append() 用。

    不是 API 契约,前端不直接发这个;由 stream 端点的 runner 收口拼出来传进来。

    id: 流式消息（assistant）由 collector 从 message_start 事件带过来——
    保证前端流式拿到的 id == 落库后的 DB id（刷新拉历史 id 不变）。
    没显式给的（user 消息）由 default_factory 生成,与 ORM 同款 uuid7。
    """

    id: UUID = Field(default_factory=uuid_compat.uuid7)
    role: MessageRole
    sender_kind: SenderKind
    sender_member_id: UUID | None = None
    content: list[dict[str, Any]]
    mentioned_member_ids: list[UUID] = []
    status: MessageStatus = MessageStatus.DONE
    error_message: str = ""