"""Message 数据模型。

Message = conversation 里的一条消息。
对齐业界协议层 role (user/assistant),加 sender_kind 区分管家/成员/真人。

content 用 jsonb blocks 数组,形态对齐前端 chat.ts:
  [
    {"type": "text", "text": "..."},
    {"type": "thinking", "text": "..."},
    {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
    {"type": "tool_result", "tool_use_id": "...", "content": [...]}
  ]
后端 → 前端零映射,前端 MessageList 直接渲染。

mentioned_member_ids 冗余字段:text 里嵌 @nickname 给人看,jsonb 数组存 id 给路由/检索用。
nickname 改名也无所谓——id 是真值。

status 三态:流式过程中的消息不入库(前端 chat-store 内存持 streaming buffer),
等 done/error/stopped 触发后才一次性 INSERT,避免频繁 UPDATE。
"""

from enum import StrEnum

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class MessageRole(StrEnum):
    """协议层角色:对齐 LangChain/OpenAI/Anthropic message role。"""

    USER = "user"
    ASSISTANT = "assistant"


class SenderKind(StrEnum):
    """业务层发送方:区分真人/管家/普通成员。"""

    USER = "user"
    SUPERVISOR = "supervisor"
    MEMBER = "member"


class MessageStatus(StrEnum):
    """终态:流式过程中不入库,落库时已是终态之一。"""

    DONE = "done"
    ERROR = "error"
    STOPPED = "stopped"


class Message(UUIDBaseModel, TimestampMixin):
    """conversation 里的一条消息。"""

    conversation = fields.ForeignKeyField(
        "models.Conversation", related_name="messages", on_delete=fields.CASCADE,
        db_index=True,
    )
    role = fields.CharEnumField(
        MessageRole, max_length=16, description="协议层角色:user/assistant",
    )
    sender_kind = fields.CharEnumField(
        SenderKind, max_length=16, description="业务层发送方:user/supervisor/member",
    )
    sender_member = fields.ForeignKeyField(
        "models.WorkspaceMember",
        related_name="messages",
        null=True,
        on_delete=fields.SET_NULL,
        description="sender_kind=member 时填;member 被踢出后保留消息、字段置 NULL",
    )

    content = fields.JSONField(
        default=list,
        description="消息内容:blocks 数组,对齐前端 chat.ts ContentBlock",
    )
    mentioned_member_ids = fields.JSONField(
        default=list,
        description="被 @ 的 member id 数组(冗余字段,给路由/反查用)",
    )

    status = fields.CharEnumField(
        MessageStatus,
        max_length=16,
        default=MessageStatus.DONE,
        description="终态:done/error/stopped(流式中不入库)",
    )
    error_message = fields.CharField(
        max_length=500, default="", description="错误友好文案(给用户看,技术细节走 log)",
    )

    class Meta:
        table = "messages"