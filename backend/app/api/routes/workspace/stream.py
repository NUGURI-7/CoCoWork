"""Workspace 对话流端点。

POST /workspaces/{wid}/conversations/{cid}/stream  →  text/event-stream

与 Playground 流端点（agent/playground.py）的三点差异：
- 历史真源在 DB：后端拉 messages → assembler 按应答者视角组装，前端只送当前一句（ConversationStreamIn）
- 全程落库：流前落 user 消息，流完 finally 落 assistant 消息（done / error / stopped 三态）
- 应答者经 build_workspace_graph 装配：没 @ → supervisor（workspace.supervisor jsonb、不在 agents 表）；@ 了 → 被 @ 的成员
"""
import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from uuid_utils import compat as uuid_compat

from app.agents.runtime import (
    MessageCollector,
    run_chat_stream,
)
from app.agents.runtime.adapter import ERROR_CODE_INTERNAL, ERROR_MESSAGE_GENERIC
from app.agents.runtime.events import EventType, sse_event
from app.agents.workspace.history_budget import should_compact
from app.agents.workspace.workspace import build_workspace_graph, validate_responder
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.core.exceptions.types import AppApiException
from app.core.observability import TraceContext
from app.models import Conversation, Message, MessageStatus, SenderKind, MessageRole, WorkspaceMember
from app.models.user import User
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.workspace import ConversationStreamIn, MessageAppend
from app.services.sandbox.attachment import resolve_refs
from app.services.workspace import (
    CompactionService,
    MessageService,
    get_compaction_service,
    get_message_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations/{conversation_id}",
    tags=["conversations"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]
CompactionServiceDep = Annotated[CompactionService, Depends(get_compaction_service)]

SSE_MEDIA_TYPE = "text/event-stream"


@router.post("/stream", summary="Workspace 对话流（supervisor 应答）")
async def conversation_stream(
        workspace_id: UUID,
        conversation_id: UUID,
        body: ConversationStreamIn,
        current_user: CurrentUserDep,
        svc: MessageServiceDep,
        compaction: CompactionServiceDep,
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
            .select_related("agent")  # build_workspace_graph 要 responder.agent.config
            .first()
        )
        if responder is None:
            raise NotFound404("被 @ 的成员不存在或已移出空间")

    # 拖进来的产物引用（决策 25）：这里只查库、只校归属，字节等沙箱装好再搬。
    # 与上面「@ 到无效成员」同一条规矩 —— 引用无效是请求错误，放在落库之前判，
    # 不把一条指向不存在文件的消息写进历史。返回的 content 已回填文件名与大小
    content, attachments = await resolve_refs(body.content, current_user)

    # ③ 先落 user —— 说出去的话即事实；prepare 失败(400)也不该让输入蒸发
    await svc.append(
        conversation_id,
        MessageAppend(
            role=MessageRole.USER,
            sender_kind=SenderKind.USER,
            # mode="json"：ref 块里的 artifact_id 是 UUID，PG 的 jsonb 不认它
            # （同 mentioned_member_ids 那句 str() 转换，一个道理）
            content=[b.model_dump(mode="json") for b in content],
            mentioned_member_ids=body.mentioned_member_ids
        ),
    )

    # 本轮 assistant 消息的 ID —— SSE 帧、DB 主键、交付区目录名共用同一个。
    # 必须赶在装配之前生成：mount 要拿它当交付区的目录名。
    # 用 compat 版：它返回标准库 uuid.UUID，Tortoise 的 UUIDField 直接吃。
    message_id = uuid_compat.uuid7()

    # ④ 开流前的配置预检（可 raise → 400 JSON，SSE 还没起）。
    #    真正的装配挪进流里了 —— 它得等压缩写完摘要才能拼历史
    await validate_responder(conversation.workspace, responder)

    collector = MessageCollector()

    async def persist_assistant(status: MessageStatus) -> None:
        """流收尾落库：assistant 消息 + touch 对话活跃时间。"""
        final = MessageStatus.ERROR if collector.saw_error else status

        # message_id 由 route 生成（见上），不必再从 MESSAGE_START 帧里捡回来 ——
        # 「早断没收到帧」这个 fallback 分支随之消失，id 一定有

        # 应答者身份：supervisor(responder=None) 或被 @ 的成员
        if responder is None:
            sender_kind, sender_member_id = SenderKind.SUPERVISOR, None
        else:
            sender_kind, sender_member_id = SenderKind.MEMBER, responder.id

        await svc.append(
            conversation_id,
            MessageAppend(
                id=message_id,
                role=MessageRole.ASSISTANT,
                sender_kind=sender_kind,
                sender_member_id=sender_member_id,
                content=collector.blocks,
                status=final,
                error_message=collector.error_message,
                prompt_tokens=collector.prompt_tokens,
                completion_tokens=collector.completion_tokens,
                token_usage=collector.usage_rows,
            ),
        )
        # usage 拿不到时（provider 不报）保留上一轮的值：清零会让判据永远不超线，
        # 层 B 就再也不触发了 —— 过时的近似值也强过失效
        update_fields = ["updated_at"]
        if collector.context_tokens > 0:
            conversation.context_tokens = collector.context_tokens
            update_fields.append("context_tokens")
        await conversation.save(update_fields=update_fields)

    async def stream():
        status = MessageStatus.STOPPED  # 悲观默认：没自然走完就是被掐
        try:
            # ⑤ 超线就先压一次历史。用户在这儿干等几秒，两帧之间前端显示进度。
            #    压缩失败只是 ok=false，不中断这一轮 —— 降级用全量历史照常跑
            if should_compact(conversation.context_tokens):
                yield sse_event(
                    EventType.COMPACT_START,
                    {"before_tokens": conversation.context_tokens},
                )
                summary = await compaction.compact(conversation, past)
                yield sse_event(EventType.COMPACT_STOP, {"ok": summary is not None})

            # ⑥ 装配（原来在流外，一行没改，只是搬进来 —— 它要读上面刚写的摘要）
            try:
                prepared = await build_workspace_graph(
                    conversation.workspace,
                    ChatStreamRequest(content=content, history=[]),
                    current_user,
                    past,
                    responder,
                    message_id=message_id,
                    conversation_id=conversation_id,
                    attachments=attachments,
                )
            except Exception as e:
                # 装配失败已经不能返 400 了（SSE 开着），只能发错误帧。
                # **必须先发 message_start** —— 前端的 error 分支要求最后一条是
                # assistant 消息，没有气泡它会静默丢掉这一帧（chat-store.ts 的
                # `if (m?.role !== 'assistant') return`），那就又变成「界面毫无反应」，
                # 正是 4035ed6 修过的那个病。
                # 业务异常带原文（「成员 X 没配模型」是说给用户听的），
                # 其余走通用文案防细节外泄（栈 / 路径 / SQL）
                logger.exception("workspace 装配失败 conversation_id=%s", conversation_id)
                yield sse_event(EventType.MESSAGE_START, {"id": str(message_id)})
                yield sse_event(EventType.ERROR, {
                    "code": ERROR_CODE_INTERNAL,
                    "message": (
                        e.message if isinstance(e, AppApiException) else ERROR_MESSAGE_GENERIC
                    ),
                })
                status = MessageStatus.ERROR
                return

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
