"""单 Agent 会话端点：员工直接打开一个 Agent 聊天，历史入库、刷新可找回。

/agents/{agent_id}/conversations/*

与 Playground（playground.py）的分工：Playground 是配置页旁的试跑场，消息不入库、
历史由前端持有；这里是正式会话，历史真源在 DB，前端只送当前这一句。

与工作空间对话流（workspace/stream.py）的差异：只有一个应答者，没有 Supervisor、
成员与视角化历史，历史按原样回放文本。

能不能看 / 能不能用由 access 模块判断：看得到才能列会话、读历史、改名删除；
能发消息（自己建的，或管理员建的且已启用）才能开流和起名 —— 已下线的 Agent
只能翻看。
"""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from uuid_utils import compat as uuid_compat

from app.agents.runtime import AgentSpec, MessageCollector, prepare_stream, run_chat_stream
from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.core.observability import TraceContext
from app.models import Agent, Message, MessageRole, MessageStatus, User
from app.schemas.agent import (
    AgentConversationOut,
    AgentConversationStreamIn,
    ChatStreamRequest,
    HistoryMessage,
    TextBlock,
)
from app.schemas.workspace import (
    ConversationTitleIn,
    ConversationTitleOut,
    ConversationUpdate,
    MessageAppend,
    MessageOut,
)
from app.services.agent.access import get_usable_agent, get_visible_agent
from app.services.agent.conversation_service import (
    AgentConversationService,
    get_agent_conversation_service,
)
from app.services.workspace import MessageService, get_message_service

router = APIRouter(prefix="/agents/{agent_id}/conversations", tags=["agent-conversations"])

SSE_MEDIA_TYPE = "text/event-stream"

CurrentUserDep = Annotated[User, Depends(get_current_user)]
ConversationsDep = Annotated[AgentConversationService, Depends(get_agent_conversation_service)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]


async def _visible_agent(agent_id: UUID, current_user: CurrentUserDep) -> Agent:
    return await get_visible_agent(current_user, agent_id)


async def _usable_agent(agent_id: UUID, current_user: CurrentUserDep) -> Agent:
    return await get_usable_agent(current_user, agent_id)


VisibleAgentDep = Annotated[Agent, Depends(_visible_agent)]
UsableAgentDep = Annotated[Agent, Depends(_usable_agent)]


def _history_from(past: list[Message]) -> list[HistoryMessage]:
    """库里的历史 → 喂给模型的历史。只回放文本：工具调用、思考、表单等过程块不进上下文。"""
    history: list[HistoryMessage] = []
    for message in past:
        blocks = [
            TextBlock(text=block["text"])
            for block in message.content
            if block.get("type") == "text" and isinstance(block.get("text"), str)
            and block["text"].strip()
        ]
        if blocks:
            history.append(HistoryMessage(role=message.role.value, content=blocks))
    return history


@router.get("", summary="列出自己在这个 Agent 下的会话")
async def list_conversations(
        agent: VisibleAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
) -> ResponseModel[list[AgentConversationOut]]:
    return success(data=await svc.list_for_agent(current_user, agent))


@router.get("/{conversation_id}/messages", summary="读取会话历史")
async def list_messages(
        conversation_id: UUID,
        agent: VisibleAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
        messages: MessageServiceDep,
) -> ResponseModel[list[MessageOut]]:
    await svc.get_owned(current_user, agent, conversation_id)
    return success(data=await messages.list_for_conversation(conversation_id))


@router.put("/{conversation_id}", summary="更新会话（改名）")
async def update_conversation(
        conversation_id: UUID,
        data: ConversationUpdate,
        agent: VisibleAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
) -> ResponseModel[AgentConversationOut]:
    conv = await svc.update(current_user, agent, conversation_id, data)
    return success(data=conv, message="更新成功")


@router.delete("/{conversation_id}", summary="删除会话")
async def delete_conversation(
        conversation_id: UUID,
        agent: VisibleAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, agent, conversation_id)
    return success(message="删除成功")


@router.post("/{conversation_id}/generate-title", summary="自动生成会话标题")
async def generate_title(
        conversation_id: UUID,
        body: ConversationTitleIn,
        agent: UsableAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
) -> ResponseModel[ConversationTitleOut]:
    title = await svc.generate_title(current_user, agent, conversation_id, body.content)
    return success(data=ConversationTitleOut(title=title))


@router.post("/{conversation_id}/stream", summary="发送消息（流式回复）")
async def conversation_stream(
        conversation_id: UUID,
        body: AgentConversationStreamIn,
        agent: UsableAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
        messages: MessageServiceDep,
) -> StreamingResponse:
    # ① 取会话（第一句话时当场建）+ 归属校验
    conversation = await svc.get_or_create(current_user, agent, conversation_id)

    # ② 拉历史 —— 必须是落 user 之前的快照，否则当前这句会在历史和本轮里各出现一次
    past = await Message.filter(conversation_id=conversation.id).order_by("created_at")

    # ③ 先落 user —— 说出去的话即事实；下面装配失败（400）也不该让输入蒸发
    await messages.append(
        conversation.id,
        MessageAppend(
            role=MessageRole.USER,
            sender_kind=None,
            content=[b.model_dump(mode="json") for b in body.content],
        ),
    )

    # 本轮 assistant 消息 ID —— SSE 帧、DB 主键、交付区目录名共用，必须赶在装配前生成
    message_id = uuid_compat.uuid7()

    # ④ 装配（可 raise → 400 JSON，SSE 还没起）。资源按 Agent 的创建者去查，
    #    会话与产物归当前用户 —— 员工用管理员建的 Agent 时两者不是同一个人
    prepared = await prepare_stream(
        AgentSpec.from_agent(agent),
        ChatStreamRequest(content=body.content, history=_history_from(past)),
        current_user,
        message_id=message_id,
        conversation_id=conversation.id,
        resource_owner=agent.created_by,
    )

    collector = MessageCollector()

    async def persist_assistant(status: MessageStatus) -> None:
        await messages.append(
            conversation.id,
            MessageAppend(
                id=message_id,
                role=MessageRole.ASSISTANT,
                sender_kind=None,
                content=collector.blocks,
                status=MessageStatus.ERROR if collector.saw_error else status,
                error_message=collector.error_message,
                prompt_tokens=collector.prompt_tokens,
                completion_tokens=collector.completion_tokens,
                token_usage=collector.usage_rows,
            ),
        )
        await conversation.save(update_fields=["updated_at"])

    async def stream():
        status = MessageStatus.STOPPED  # 悲观默认：没自然走完就是被掐
        try:
            async for sse in run_chat_stream(
                    prepared.graph,
                    prepared.messages,
                    message_id=message_id,
                    collect=prepared.collect,
                    close=prepared.close,
                    display_names=prepared.display_names,
                    sink=collector.feed,
                    usage=lambda: collector.usage_summary,
                    trace=TraceContext(
                        user_id=str(current_user.id),
                        session_id=str(conversation.id),
                        name="agent_chat",
                        tags=["agent_chat"],
                        metadata={"agent_id": str(agent.id)},
                    ),
            ):
                yield sse
            status = MessageStatus.DONE
        finally:
            # 用户中断时本 task 已被 cancel；shield 保证落库协程跑完 ——
            # 中断恰恰是最不能丢落库的路径：半截消息也是历史
            await asyncio.shield(persist_assistant(status))

    return StreamingResponse(stream(), media_type=SSE_MEDIA_TYPE)
