from typing import Any
from uuid import UUID

from app.core.exceptions import NotFound404
from app.models import Conversation, Message, MessageStatus, User
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
            prompt_tokens=data.prompt_tokens,
            completion_tokens=data.completion_tokens,
            token_usage=data.token_usage,
        )

        return MessageOut.model_validate(message)

    async def continue_message(
        self, message_id: UUID, data: MessageAppend, *, answer: dict[str, Any],
    ) -> MessageOut | None:
        """给一条卡在人工确认上的消息续写 —— 「继续」那条流跑完后调。

        与 append 的分工：append **新建**一条消息，本方法把新内容接到**同一条**
        上。用户看到的是一条连贯的回复中间插了张表单，而不是被切成两条气泡；
        checkpoint 的 thread_id 用的也是这条消息的 id，两边对得上。

        content 追加不覆盖：中断前已经说过的话要留着。
        token 三项同理累加 —— 一条消息的用量是两段之和。

        status 进 WHERE 而不是查完再判断，可以挡掉大部分重复提交；但查与写
        是两步，并非严格的并发锁 —— 真正兜住的是 LangGraph 那层：同一个存档
        恢复过一次之后，第二次就没有中断在等着了。

        返回 None = 消息不存在或已不在中断态，由调用方翻成 4xx。
        """
        message = await Message.filter(
            id=message_id, status=MessageStatus.INTERRUPTED
        ).first()
        if message is None:
            return None

        # 把答案回填进最后一个未作答的表单块 —— 历史里就能看到「当时问了什么、
        # 我答了什么」，而不是只剩一个空表单。从后往前找：一条消息可能问过好
        # 几轮，只有最后那个是这次答的
        for block in reversed(message.content):
            if block.get("type") == "ask" and block.get("answer") is None:
                block["answer"] = answer
                break

        message.content = [*message.content, *data.content]
        message.status = data.status
        message.error_message = data.error_message
        message.prompt_tokens += data.prompt_tokens
        message.completion_tokens += data.completion_tokens
        message.token_usage = [*message.token_usage, *data.token_usage]

        await message.save(update_fields=[
            "content", "status", "error_message",
            "prompt_tokens", "completion_tokens", "token_usage", "updated_at",
        ])
        return MessageOut.model_validate(message)


async def get_message_service() -> MessageService:
    return MessageService()






