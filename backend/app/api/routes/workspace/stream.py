"""Workspace 对话流端点。

POST /workspaces/{wid}/conversations/{cid}/stream  →  text/event-stream

与 Playground 流端点（agent/playground.py）的三点差异：
- 历史真源在 DB：后端拉 messages → assembler 按应答者视角组装，前端只送当前一句（ConversationStreamIn）
- 全程落库：流前落 user 消息，流完 finally 落 assistant 消息（done / error / stopped 三态）
- 应答者经 build_workspace_graph 装配：没 @ → supervisor（workspace.supervisor jsonb、不在 agents 表）；@ 了 → 被 @ 的成员
"""
import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agents.runtime import (
    MessageCollector,
    run_chat_stream,
)
from app.agents.workspace.workspace import build_workspace_graph
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.core.observability import TraceContext
from app.models import Conversation, Message, MessageStatus, SenderKind, MessageRole, WorkspaceMember
from app.models.user import User
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.workspace import ConversationStreamIn, MessageAppend
from app.services.workspace import MessageService, get_message_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations/{conversation_id}",
    tags=["conversations"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]

SSE_MEDIA_TYPE = "text/event-stream"


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

    # 选应答者：没 @ → supervisor(None)；@ 了 → 第一个被 @ 的成员（v1 单 @）
    # 放在落 user 之前：@ 到无效成员是请求错误,直接 404、不落库
    responder: WorkspaceMember | None = None
    if body.mentioned_member_ids:
        responder = (
            await WorkspaceMember.filter(
                id=body.mentioned_member_ids[0],
                workspace_id=workspace_id
            )
            .select_related("agent") # build_workspace_graph 要 responder.agent.config
            .first()
        )
        if responder is None:
            raise NotFound404("被 @ 的成员不存在或已移出空间")


    # ③ 先落 user —— 说出去的话即事实；prepare 失败(400)也不该让输入蒸发
    await svc.append(
        conversation_id,
        MessageAppend(
            role=MessageRole.USER,
            sender_kind=SenderKind.USER,
            content=[b.model_dump() for b in body.content],
            mentioned_member_ids=body.mentioned_member_ids
        ),
    )

    # ④ supervisor 装配（可 raise → 400 JSON，SSE 还没起）
    graph, lc_messages = await build_workspace_graph(
        conversation.workspace,
        ChatStreamRequest(content=body.content, history=[]),
        current_user,
        past,
        responder,
    )

    collector = MessageCollector()

    async def persist_assistant(status: MessageStatus) -> None:
        """流收尾落库：assistant 消息 + touch 对话活跃时间。"""
        final = MessageStatus.ERROR if collector.saw_error else status
        # message_id 来自 MESSAGE_START 帧；极端早断没收到时不传，
        # 让 MessageAppend 的 default_factory 自己造
        keyed = {"id": collector.message_id} if collector.message_id else {}

        # 应答者身份：supervisor(responder=None) 或被 @ 的成员
        if responder is None:
            sender_kind, sender_member_id = SenderKind.SUPERVISOR, None
        else:
            sender_kind, sender_member_id = SenderKind.MEMBER, responder.id

        await svc.append(
            conversation_id,
            MessageAppend(
                **keyed,
                role=MessageRole.ASSISTANT,
                sender_kind=sender_kind,
                sender_member_id=sender_member_id,
                content=collector.blocks,
                status=final,
                error_message=collector.error_message,
            ),
        )
        await conversation.save(update_fields=["updated_at"])

    async def stream():
        status = MessageStatus.STOPPED  # 悲观默认：没自然走完就是被掐
        try:
            async for sse in run_chat_stream(
                graph,
                lc_messages,
                sink=collector.feed,
                trace=TraceContext(
                    user_id=str(current_user.id),
                    session_id=str(conversation_id),
                    name="workspace_chat",
                    tags=["workspace_chat"],
                    metadata={
                        "workspace_id": str(workspace_id),
                        "responder": "supervisor" if responder is None else str(responder.id),
                    },
                ),
            ):
                yield sse
            status = MessageStatus.DONE  # 自然走到这行 = 完整流完
        finally:
            # 用户中断时本 task 已被 cancel，finally 里裸 await 可能被再次打断；
            # shield 给落库协程穿防弹衣 —— 外层取消不波及它，INSERT 必然跑完。
            # 而中断（stopped）恰恰是最不能丢落库的路径：半截消息也是历史。
            await asyncio.shield(persist_assistant(status))

    return StreamingResponse(stream(), media_type=SSE_MEDIA_TYPE)
