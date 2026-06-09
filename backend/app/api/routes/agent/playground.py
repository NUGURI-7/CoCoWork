"""Agent Playground 流式对话端点。

POST /agents/{agent_id}/playground/stream  →  text/event-stream

与既有 CRUD 端点不同：
- 返 StreamingResponse、非 ResponseModel JSON 壳
- 不走 service.get_by_id（它返 AgentOut Pydantic 转换层）——这里直接 ORM
  查一次顺便做归属校验，再用 AgentSpec.from_agent(agent) 转出 runner 契约；
  SSE 路径不返 JSON、不必绕 schema 层
- prepare_stream 校验失败 raise → FastAPI handler 翻 400 JSON（SSE 还没起）
- StreamingResponse 一旦返、流跑中所有错误都走 SSE error 帧（adapter 已脱敏）
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agents.runtime import prepare_stream, run_chat_stream, AgentSpec
from app.core.depends import get_current_user
from app.core.exceptions import NotFound404
from app.models import Agent
from app.models.user import User
from app.schemas.agent import ChatStreamRequest

router = APIRouter(prefix="/agents", tags=["agents"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]

SSE_MEDIA_TYPE = "text/event-stream"


@router.post(
    "/{agent_id}/playground/stream",
    summary="Playground 流式对话",
)
async def playground_stream(
        agent_id: UUID,
        body: ChatStreamRequest,
        current_user: CurrentUserDep,
) -> StreamingResponse:
    agent = await Agent.filter(created_by=current_user, id=agent_id).first()
    if agent is None:
        raise NotFound404("Agent 不存在")

    graph, messages = await prepare_stream(AgentSpec.from_agent(agent), body, current_user)

    return StreamingResponse(
        run_chat_stream(graph, messages),
        media_type=SSE_MEDIA_TYPE,
    )
