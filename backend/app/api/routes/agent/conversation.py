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
import logging
from dataclasses import replace
from functools import partial
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command
from uuid_utils import compat as uuid_compat

from app.agents.runtime import AgentSpec, MessageCollector, prepare_stream, run_chat_stream
from app.agents.runtime.blocks import TextBlock as ReplayTextBlock, parse_blocks
from app.agents.runtime.history_replay import has_oversized, replay_own_turn
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.db.checkpointer import get_checkpointer
from app.core.http import ResponseModel, success
from app.core.observability import TraceContext
from app.models import Agent, Message, MessageRole, MessageStatus, User
from app.models.sandbox import SandboxArtifact
from app.schemas.agent import (
    AgentConversationOut,
    AgentConversationStreamIn,
    ChatStreamRequest,
    TextBlock,
)
from app.schemas.agent.interrupt_schema import AskAnswer
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
from app.tools.tool_result_fetch import ToolResultFetchTool

logger = logging.getLogger(__name__)

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


def _history_from(past: list[Message]) -> tuple[list[BaseMessage], bool]:
    """库里的历史 → 喂给模型的消息，以及其中有没有被截断的工具结果。

    用户发言取文本；Agent 的回复还原成当初的调用形状（工具调用 + 配对结果），
    与工作空间回放应答者自己那条历史同一套。思考与表单不回放。
    """
    history: list[BaseMessage] = []
    truncated = False
    for message in past:
        blocks = parse_blocks(message.content)
        if message.role == MessageRole.USER:
            text = "".join(b.text for b in blocks if isinstance(b, ReplayTextBlock) and b.text)
            if text.strip():
                history.append(HumanMessage(text))
        else:
            truncated = truncated or has_oversized(blocks)
            history.extend(replay_own_turn(blocks, message.id))
    return history, truncated


def _assistant_append(
        collector: MessageCollector, *, message_id: UUID, status: MessageStatus,
) -> MessageAppend:
    """首轮新建与续跑续写共用同一份字段组装。"""
    return MessageAppend(
        id=message_id,
        role=MessageRole.ASSISTANT,
        sender_kind=None,
        content=collector.blocks,
        status=MessageStatus.ERROR if collector.saw_error else status,
        error_message=collector.error_message,
        prompt_tokens=collector.prompt_tokens,
        completion_tokens=collector.completion_tokens,
        token_usage=collector.usage_rows,
    )


async def _message_artifacts(message_id: UUID) -> list[SandboxArtifact]:
    """本条回复挂着的产物（后台任务做出来的文件），回复结束时推给前端。"""
    return await SandboxArtifact.filter(message_id=message_id).order_by("filename")


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
    await messages.expire_pending(conversation.id)
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
    history, truncated = _history_from(past)

    # ④ 装配（可 raise → 400 JSON，SSE 还没起）
    prepared = await prepare_stream(
        AgentSpec.from_agent(agent),
        ChatStreamRequest(content=body.content, history=[]),
        current_user,
        message_id=message_id,
        conversation_id=conversation.id,
        checkpointer=get_checkpointer(),
        # 历史里有被截断的结果才挂取回工具 —— 与工作空间同一条规矩：有指引就有工具
        extra_tools=[ToolResultFetchTool(conversation_id=conversation.id)] if truncated else [],
    )
    # prepare_stream 只收纯文本历史；还原好的调用形状拼在本轮输入之前
    prepared = replace(prepared, messages=[*history, *prepared.messages])

    collector = MessageCollector()

    async def persist_assistant(status: MessageStatus) -> None:
        await messages.append(
            conversation.id,
            _assistant_append(collector, message_id=message_id, status=status),
        )
        await conversation.save(update_fields=["updated_at"])

    async def stream():
        status = MessageStatus.STOPPED  # 悲观默认：没自然走完就是被掐
        try:
            async for sse in run_chat_stream(
                    prepared.graph,
                    prepared.messages,
                    message_id=message_id,
                    collect=prepared.collect or partial(_message_artifacts, message_id),
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
            status = (
                MessageStatus.INTERRUPTED if collector.saw_interrupt else MessageStatus.DONE
            )
        finally:
            # 用户中断时本 task 已被 cancel；shield 保证落库协程跑完 ——
            # 中断恰恰是最不能丢落库的路径：半截消息也是历史
            await asyncio.shield(persist_assistant(status))

    return StreamingResponse(stream(), media_type=SSE_MEDIA_TYPE)


@router.post("/{conversation_id}/messages/{message_id}/resume", summary="提交表单，从存档接着执行")
async def resume_stream(
        conversation_id: UUID,
        message_id: UUID,
        body: AskAnswer,
        agent: UsableAgentDep,
        current_user: CurrentUserDep,
        svc: ConversationsDep,
        messages: MessageServiceDep,
) -> StreamingResponse:
    conversation = await svc.get_owned(current_user, agent, conversation_id)
    pending = await Message.filter(
        id=message_id, conversation_id=conversation.id, status=MessageStatus.INTERRUPTED,
    ).exists()
    if not pending:
        raise NotFound404("这条消息不存在，或已经不在等待确认的状态")

    prepared = await prepare_stream(
        AgentSpec.from_agent(agent),
        ChatStreamRequest(content=[TextBlock(text="")], history=[]),
        current_user,
        message_id=message_id,
        conversation_id=conversation.id,
        checkpointer=get_checkpointer(),
    )
    collector = MessageCollector()

    async def persist_continuation(status: MessageStatus) -> None:
        updated = await messages.continue_message(
            message_id,
            _assistant_append(collector, message_id=message_id, status=status),
            answer=body.model_dump(mode="json"),
        )
        if updated is None:
            logger.warning("续写落库落空，消息已不在中断态 message_id=%s", message_id)
        await conversation.save(update_fields=["updated_at"])

    async def stream():
        status = MessageStatus.STOPPED
        try:
            async for sse in run_chat_stream(
                    prepared.graph,
                    Command(resume=body.model_dump(mode="json")),
                    message_id=message_id,
                    collect=prepared.collect or partial(_message_artifacts, message_id),
                    close=prepared.close,
                    display_names=prepared.display_names,
                    sink=collector.feed,
                    usage=lambda: collector.usage_summary,
                    trace=TraceContext(
                        user_id=str(current_user.id),
                        session_id=str(conversation.id),
                        name="agent_chat_resume",
                        tags=["agent_chat", "resume"],
                        metadata={"agent_id": str(agent.id)},
                    ),
            ):
                yield sse
            status = (
                MessageStatus.INTERRUPTED if collector.saw_interrupt else MessageStatus.DONE
            )
        finally:
            await asyncio.shield(persist_continuation(status))

    return StreamingResponse(stream(), media_type=SSE_MEDIA_TYPE)
