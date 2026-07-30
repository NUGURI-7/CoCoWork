from uuid import UUID

from app.core.exceptions import NotFound404
from app.models import Conversation, Message, User
from app.schemas.sandbox import ArtifactOut
from app.schemas.workspace import MessageAppend, MessageOut
from app.services.sandbox.artifact import group_by_message


class MessageService:
    """Message 服务。

    不开标准 REST CRUD:
    - 写消息走对话流端点(stream handler 流完后调 append)
    - 编辑 / 删消息 v1 不做(消息是历史事实)

    只暴露:
    - list_in_conversation: 列对话历史(前端首次进对话拉历史)
    - append: 流完一条消息后落库(service 内部, 不做 user 校验,
      调用方负责完成 user/workspace/conversation 校验)
    """

    async def list_in_conversation(
        self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> list[MessageOut]:
        """列 conversation 下的消息, 按 created_at 升序(老→新)。

        三层归属校验靠 ORM JOIN 一次过(conversation → workspace → user)。
        """
        conv_exists = await Conversation.filter(
            id=conversation_id,
            workspace_id=workspace_id,
            workspace__created_by=user,
        ).exists()
        if not conv_exists:
            raise NotFound404("Conversation 不存在")

        messages = await Message.filter(
            conversation_id=conversation_id,
        ).order_by("created_at")

        # 归组逻辑收在 sandbox.artifact 里，与视角化历史装配共用（决策 24）
        grouped = await group_by_message(conversation_id)

        result: list[MessageOut] = []
        for m in messages:
            out = MessageOut.model_validate(m)
            out.artifacts = [ArtifactOut.model_validate(a) for a in grouped[m.id]]
            result.append(out)

        return result


    async def append(
        self, conversation_id: UUID, data: MessageAppend,
    ) -> MessageOut:
        """插一条消息(service 内部用, stream handler 流完后调)。

        不做归属校验:调用方(stream 端点)已经完成 user/workspace/conversation 校验。
        mentioned_member_ids 落 jsonb 时 UUID → str(PG jsonb 不认 UUID 类型,
        读出来 Pydantic 自动 str → UUID 反序列化)。
        """

        message = await Message.create(
            id=data.id,
            conversation_id=conversation_id,
            role=data.role,
            sender_kind=data.sender_kind,
            sender_member_id=data.sender_member_id,
            content=data.content,
            mentioned_member_ids=[str(uid) for uid in data.mentioned_member_ids],
            status=data.status,
            error_message=data.error_message,
        )

        return MessageOut.model_validate(message)

async def get_message_service() -> MessageService:
    return MessageService()






