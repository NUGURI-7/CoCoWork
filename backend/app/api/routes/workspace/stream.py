"""Workspace 对话流端点。

POST /workspaces/{wid}/conversations/{cid}/stream  →  text/event-stream

与 Playground 流端点（agent/playground.py）的三点差异：
- 历史真源在 DB：后端拉 messages 拼 history，前端只送当前一句（ConversationStreamIn）
- 全程落库：流前落 user 消息，流完 finally 落 assistant 消息（done / error / stopped 三态）
- supervisor 不在 agents 表：AgentSpec.from_jsonb(workspace.supervisor) 直接装配
"""
import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agents.runtime import (
    AgentSpec,
    MessageCollector,
    run_chat_stream,
)
from app.agents.workspace.workspace import build_workspace_graph
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.models import Conversation, Message, MessageStatus, SenderKind, MessageRole
from app.models.user import User
from app.schemas.agent.chat_schema import ChatStreamRequest, HistoryMessage, TextBlock
from app.schemas.workspace import ConversationStreamIn, MessageAppend
from app.services.workspace import MessageService, get_message_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations/{conversation_id}",
    tags=["conversations"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]

SSE_MEDIA_TYPE = "text/event-stream"


def _db_messages_to_history(messages: list[Message]) -> list[HistoryMessage]:
    """DB 消息 → LLM 上下文 history，只回放 text 块（存而不喂）。

    thinking 是模型内部草稿、tool 轨迹回放吃上下文且易把模型带偏；
    DB 留完整事实给前端还原，上下文只给模型有用的部分。
    整条凑不出非空 text 的消息（纯工具轮 / 刚开口就被掐）直接跳过。
    """
    history: list[HistoryMessage] = []

    for m in messages:
        texts = [
            TextBlock(text=b["text"])
            for b in m.content
            if b.get("type") == "text" and b.get("text")
        ]
        if not texts:
            continue
        history.append(HistoryMessage(role=m.role, content=texts))
    return history


@router.post("/stream", summary="Workspace 对话流（supervisor 应答）")
async def conversation_stream(
        workspace_id: UUID,
        conversation_id: UUID,
        body: ConversationStreamIn,
        current_user: CurrentUserDep,
        svc: MessageServiceDep,
) -> StreamingResponse:
    # ① 归属校验 + 取数：JOIN 一次过；prefetch workspace 拿 supervisor jsonb
    conversation = (
        await Conversation.filter(
            id=conversation_id,
            workspace_id=workspace_id,
            workspace__created_by=current_user,
        )
        .prefetch_related("workspace")
        .first()
    )

    if conversation is None:
        raise NotFound404("Conversation 不存在")

    # ② 拉历史 —— 必须是"落 user 之前"的快照，否则当前这句 history / content 双送
    past = await Message.filter(conversation_id=conversation_id).order_by("created_at")
    history = _db_messages_to_history(past)

    # ③ 先落 user —— 说出去的话即事实；prepare 失败(400)也不该让输入蒸发
    await svc.append(
        conversation_id,
        MessageAppend(
            role=MessageRole.USER,
            sender_kind=SenderKind.USER,
            content=[b.model_dump() for b in body.content],
        ),
    )

    # ④ supervisor jsonb → AgentSpec → 装配（可 raise → 400 JSON，SSE 还没起）
    spec = AgentSpec.from_jsonb(conversation.workspace.supervisor)
    graph, lc_messages = await build_workspace_graph(
        conversation.workspace,
        ChatStreamRequest(content=body.content, history=history),
        current_user,
    )

    collector = MessageCollector()

    async def persist_assistant(status: MessageStatus) -> None:
        """流收尾落库：assistant 消息 + touch 对话活跃时间。"""
        final = MessageStatus.ERROR if collector.saw_error else status
        # message_id 来自 MESSAGE_START 帧；极端早断没收到时不传，
        # 让 MessageAppend 的 default_factory 自己造
        keyed = {"id": collector.message_id} if collector.message_id else {}
        await svc.append(
            conversation_id,
            MessageAppend(
                **keyed,
                role=MessageRole.ASSISTANT,
                sender_kind=SenderKind.SUPERVISOR,
                content=collector.blocks,
                status=final,
                error_message=collector.error_message,
            ),
        )
        await conversation.save(update_fields=["updated_at"])

    async def stream():
        status = MessageStatus.STOPPED  # 悲观默认：没自然走完就是被掐
        try:
            async for sse in run_chat_stream(graph, lc_messages, sink=collector.feed):
                yield sse
            status = MessageStatus.DONE  # 自然走到这行 = 完整流完
        finally:
            # 用户中断时本 task 已被 cancel，finally 里裸 await 可能被再次打断；
            # shield 给落库协程穿防弹衣 —— 外层取消不波及它，INSERT 必然跑完。
            # 而中断（stopped）恰恰是最不能丢落库的路径：半截消息也是历史。
            await asyncio.shield(persist_assistant(status))

    return StreamingResponse(stream(), media_type=SSE_MEDIA_TYPE)
