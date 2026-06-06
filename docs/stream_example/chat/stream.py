"""
    @project: DaisyWind
    @Author: niu
    @file: stream.py.py
    @date: 2026/4/12 15:15
    @desc: SSE 流式对话端点
"""
import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic_ai import Agent, PartStartEvent, TextPart, PartDeltaEvent, TextPartDelta, PartEndEvent, \
    AgentRunResultEvent, ToolCallPart, ToolCallPartDelta, FunctionToolResultEvent, FilePart
from starlette.responses import StreamingResponse

from backend.app.agents.chat_agent import build_chat_agent
from backend.app.agents.deps import AgentDeps
from backend.app.agents.pricing import calc_cost
from backend.app.core.depends import get_current_user
from backend.app.core.storage import r2_storage
from backend.app.models import User, Conversation
from backend.app.schemas.chat_schema import ChatRequest, MessageRole, TextBlock, ToolUseBlock, ImageBlock
from backend.app.services.chat_service import ChatService
from backend.app.services.sse import sse_event

router = APIRouter()


async def stream_generator(
        agent: Agent,
        deps: AgentDeps,
        user_input: str,
        llm_messages: list[dict],
        conversation: Conversation,
        created: bool,
        request: ChatRequest
):
    """SSE async generator：驱动 Agent 流式输出并转换为 SSE 事件。

    本函数同时承担两件事：
    1. 把 PydanticAI 的事件流翻译成前端约定的 SSE 事件
    2. 把本轮 assistant 输出的所有 block（text + tool_use）按顺序聚合并落库
    """
    # 所有 block 按插入顺序存放；list 下标 = 对外 SSE 的 index（全局单调、绝不复用）
    # 最后按插入顺序直接持久化
    blocks: list[dict] = []

    # PydanticAI 的 part.index 是"每一轮 ModelResponse 内的序号"，跨轮会重置
    # 所以需要"当前轮 part.index -> blocks list 下标"的翻译表
    # 每次 FunctionToolResultEvent（= 进入下一轮）清空一次
    part_idx_to_list_idx: dict[int, int] = {}

    # tool_call_id 全局唯一，FunctionToolResultEvent 用它回查 list 下标
    tool_call_id_to_list_idx: dict[str, int] = {}

    # 工具入参累积 JSON 字符串，key 是 blocks list 下标（全局唯一）
    tool_input_buffer: dict[int, str] = {}

    yield sse_event("message_start", {
        "conversation_uuid": str(conversation.uuid),
        "message_uuid": request.message_uuid,
        "model": request.model,
        "provider": request.provider
    })

    is_image_model = request.provider == "gemini" and "image" in request.model
    pending_image_id: str | None = None
    if is_image_model:
        pending_image_id = f"ima_{uuid4().hex}"
        blocks.append({
            "type":"image",
            "id": pending_image_id,
            "status": "loading",
            "url": None,
            "message": None
        })
        yield sse_event("image",{
            "id": pending_image_id,
            "status": "loading"
        })

    try:
        async for event in agent.run_stream_events(
                user_input,
                deps=deps,
                message_history=llm_messages
        ):
            # ============ 文本块 ============
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                blocks.append({"type": "text", "text": event.part.content or ""})
                li = len(blocks) - 1
                part_idx_to_list_idx[event.index] = li

                yield sse_event("content_block_start", {
                    "index": li,
                    "type": "text"
                })

                if event.part.content:
                    yield sse_event("content_block_delta", {
                        "index": li,
                        "type": "text_delta",
                        "text": event.part.content
                    })
            # TODO P1: handle ThinkingPart → content_block_start(type="thinking")
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                li = part_idx_to_list_idx.get(event.index)
                if li is None:
                    continue
                block = blocks[li]
                if block and block.get("type") == "text":
                    block["text"] += event.delta.content_delta
                yield sse_event("content_block_delta", {
                    "index": li,
                    "type": "text_delta",
                    "text": event.delta.content_delta
                })

            # ============ Tool 调用块 ============
            elif isinstance(event, PartStartEvent) and isinstance(event.part, ToolCallPart):
                tool_name = event.part.tool_name
                tool_call_id = event.part.tool_call_id
                blocks.append({
                    "type": "tool_use",
                    "id": tool_call_id,
                    "name": tool_name,
                    "input": {},
                    "status": "success",
                    "output": None,
                })
                li = len(blocks) - 1
                part_idx_to_list_idx[event.index] = li
                tool_call_id_to_list_idx[tool_call_id] = li
                tool_input_buffer[li] = ""
                yield sse_event("tool_use_start", {
                    "index": li,
                    "id": tool_call_id,
                    "name": tool_name,
                    "input_preview": "",
                })

            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, ToolCallPartDelta):
                li = part_idx_to_list_idx.get(event.index)
                if li is None:
                    continue
                delta_text = event.delta.args_delta or ""
                tool_input_buffer[li] = tool_input_buffer.get(li, "") + delta_text
                block = blocks[li]

                tool_call_id = block["id"] if block.get("type") == "tool_use" else ""

                yield sse_event("tool_use_delta", {
                    "index": li,
                    "id": tool_call_id,
                    "type": "input_json_delta",
                    "partial_json": delta_text
                })

            # ============ Part 结束（区分 text / tool_use） ============

            elif isinstance(event, PartEndEvent):
                li = part_idx_to_list_idx.get(event.index)
                if li is None:
                    continue
                block = blocks[li]
                if block and block.get("type") == "text":
                    yield sse_event("content_block_stop", {"index": li})
                elif block and block.get("type") == "tool_use":
                    # 把累积的 JSON 字符串解析成 dict
                    try:
                        parsed_input = json.loads(tool_input_buffer.get(li) or "{}")
                    except Exception:
                        parsed_input = {}
                    block["input"] = parsed_input
                    yield sse_event("tool_use_stop", {
                        "index": li,
                        "id": block["id"]
                    })

            # ============ Tool 执行结果 ============
            elif isinstance(event, FunctionToolResultEvent):
                tool_call_id = event.result.tool_call_id
                li = tool_call_id_to_list_idx.get(tool_call_id)

                if li is not None:
                    block = blocks[li]
                    block["output"] = event.result.content
                    block["status"] = "success"

                    # 给前端生成一个摘要（result_data 仍然附带完整内容）
                    if isinstance(event.result.content, list):
                        summary = f"返回 {len(event.result.content)} 项结果"
                    elif isinstance(event.result.content, str):
                        summary = event.result.content[:100]
                    else:
                        summary = str(event.result.content)[:100]

                    yield sse_event("tool_result", {
                        "index": li,
                        "id": tool_call_id,
                        "name": block["name"],
                        "status": "success",
                        "result_summary": summary,
                        "result_data": event.result.content
                    })
                # 一轮结束，下一轮 PydanticAI part.index 会从 0 重新计数
                # 必须清掉旧映射，否则下一轮的 delta 会路由到上一轮的 block
                part_idx_to_list_idx.clear()

            # ============ 图片块（Nano Banana / Gemini 图像输出） ============
            elif isinstance(event, PartStartEvent) and isinstance(event.part, FilePart):
                binary = event.part.content
                image_bytes = binary.data
                media_type = binary.media_type    # "image/jpeg" / "image/png" / ...
                ext = media_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"

                object_name = f"chat/gemini_generated/{deps.user.id}/{uuid4().hex}.{ext}"
                # 优先复用已经预发出去的 loading 占位（多图场景下后续的才新建）
                if pending_image_id is not None:
                    placeholder_id = pending_image_id
                    li = next(i for i,b in enumerate(blocks) if b.get("id") == placeholder_id)
                    part_idx_to_list_idx[event.index] = li
                    pending_image_id = None  # 标记已被认领
                else:

                    placeholder_id = f"ima_{uuid4().hex}"

                    blocks.append({
                        "type": "image",
                        "id": placeholder_id,
                        "status": "loading",
                        "url": None,
                        "message": None,
                    })
                    li = len(blocks) - 1
                    part_idx_to_list_idx[event.index] = li

                    # 先发 loading 让前端立即显示 Trefoil 动画
                    yield sse_event("image", {
                        "id": placeholder_id,
                        "status": "loading",
                    })

                try:
                    url = await asyncio.to_thread(
                        r2_storage.upload_bytes,
                        image_bytes,
                        object_name,
                        media_type
                    )
                    blocks[li]["status"] = "ready"
                    blocks[li]["url"] = url
                    yield sse_event("image",{
                        "id": placeholder_id,
                        "status": "ready",
                        "url": url,
                    })
                except Exception as e:
                    blocks[li]["status"] = "error"
                    blocks[li]["message"] = str(e)
                    yield sse_event("image",{
                        "id": placeholder_id,
                        "status": "error",
                        "message": str(e)
                    })

            # ============ Agent 运行完成 ============

            elif isinstance(event, AgentRunResultEvent):
                usage = event.result.usage()
                # 统计本次输出中成功上传的图片张数用于计费
                image_count = sum(
                    1 for b in blocks
                    if b.get("type") == "image" and b.get("status") == "ready"
                )
                cost = calc_cost(request.model, usage.input_tokens, usage.output_tokens, image_count=image_count)
                yield sse_event("message_delta", {
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "cost": cost
                    }
                })

        # 图像模型兜底：预发的 loading 占位没被认领的处理
        if pending_image_id is not None:
            # 检查这一轮有没有任何 text block 产生
            has_text = any(
                b.get("type") == "text" and (b.get("text") or "").strip()
                for b in blocks
            )
            if has_text:
                # 模型给了文字解释（拒绝/澄清），移除幽灵 loading 占位
                blocks[:] = [b for b in blocks if b.get("id") != pending_image_id]

                yield sse_event("image", {
                    "id": pending_image_id,
                    "status": "removed"
                })
            else:
                # 完全没图也没文字，标记为 error
                for b in blocks:
                    if b.get("id") == pending_image_id:
                        b["status"] = "error"
                        b["message"] = "No image returned"
                        break
                yield sse_event("image", {
                    "id": pending_image_id,
                    "status": "error",
                    "message": "No image returned",
                })
        yield sse_event("message_stop", {})

    except Exception as e:
        yield sse_event("error", {
            "code": "internal_error",
            "message": str(e)
        })

    finally:
        # 持久化 assistant message：blocks 已是插入顺序，直接遍历
        if blocks:
            content_blocks: list = []
            for ob in blocks:
                if ob["type"] == "text":
                    if ob.get("text"):
                        content_blocks.append(TextBlock(type="text", text=ob["text"]))
                elif ob["type"] == "tool_use":
                    content_blocks.append(ToolUseBlock(
                        type="tool_use",
                        id=ob["id"],
                        name=ob["name"],
                        input=ob.get("input") or {},
                        status=ob.get("status", "success"),
                        output=ob.get("output"),
                    ))
                elif ob["type"] == "image":
            # 只持久化已成功上传的图片；loading/error 的丢弃
                    if ob.get("status") == "ready" and ob.get("url"):
                        content_blocks.append(ImageBlock(
                            type="image",
                            id=ob["id"],
                            status="ready",
                            url=ob["url"],
                        ))

            if content_blocks:
                await ChatService.add_message(
                    conversation, MessageRole.ASSISTANT, content_blocks
                )

            if created:
                await ChatService.update_title_from_first_message(conversation)


@router.post("/send")
async def send_message(request: ChatRequest, user: User = Depends(get_current_user)):
    """发送消息，返回 SSE 流。"""

    conversation, created = await ChatService.get_or_create_conversation(
        uuid=request.conversation_uuid,
        user=user,
        provider=request.provider,
        model=request.model
    )

    await ChatService.add_message(conversation, MessageRole.USER, request.content)

    llm_messages = await ChatService.build_llm_messages(conversation)

    # 给 agent 的 user_input 必须是字符串，从 block 数组里提取所有 text block
    user_input = "".join(b.text for b in request.content if b.type == "text")

    agent = build_chat_agent(request.provider, request.model)
    deps = AgentDeps(user=user, conversation=conversation)

    return StreamingResponse(
        stream_generator(
            agent=agent,
            deps=deps,
            user_input=user_input,
            llm_messages=llm_messages[:-1],  # 最后一条是刚存的 user msg，已作为 user_input 传入
            conversation=conversation,
            created=created,
            request=request
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
