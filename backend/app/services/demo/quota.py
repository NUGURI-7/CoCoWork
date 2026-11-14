"""官网体验的调用限额：只约束临时账号，正式用户直接放行。"""

from datetime import datetime, time, timezone

from fastapi import Depends, Request
from redis import asyncio as aioredis
from tortoise.expressions import Subquery
from tortoise.functions import Sum

from app.core.config import settings
from app.core.depends import get_current_user
from app.core.exceptions import TooManyRequests429, ValidationException
from app.core.redis import get_redis
from app.models import Conversation, Message, User

SECONDS_PER_DAY = 24 * 60 * 60


async def guest_send_quota(
    request: Request,
    user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    if not user.is_guest:
        return
    _ensure_input_length(await _request_text(request))
    await _ensure_token_budget()
    target_id = request.path_params.get("workspace_id") or request.path_params.get("agent_id")
    await _consume_scene_quota(redis, user, target_id)


async def guest_token_budget(user: User = Depends(get_current_user)) -> None:
    if user.is_guest:
        await _ensure_token_budget()


async def _request_text(request: Request) -> str:
    try:
        body = await request.json()
    except ValueError:
        return ""
    blocks = body.get("content", []) if isinstance(body, dict) else []
    return "".join(
        b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
    )


def _ensure_input_length(text: str) -> None:
    if len(text) > settings.DEMO_MAX_INPUT_CHARS:
        raise ValidationException(f"体验版单条消息不超过 {settings.DEMO_MAX_INPUT_CHARS} 字")


async def _ensure_token_budget() -> None:
    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    guest_conversations = Subquery(Conversation.filter(created_by__is_guest=True).values("id"))
    row = await (
        Message.filter(created_at__gte=today_start, conversation_id__in=guest_conversations)
        .annotate(prompt=Sum("prompt_tokens"), completion=Sum("completion_tokens"))
        .first()
        .values("prompt", "completion")
    )
    used = (row["prompt"] or 0) + (row["completion"] or 0) if row else 0
    if used >= settings.DEMO_DAILY_TOKEN_BUDGET:
        raise TooManyRequests429("今天的体验额度已用完，请明天再来")


async def _consume_scene_quota(redis: aioredis.Redis, user: User, target_id: str | None) -> None:
    day = datetime.now(timezone.utc).date().isoformat()
    key = f"demo:messages:{day}:{user.id}:{target_id}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, SECONDS_PER_DAY, nx=True)
        count, _ = await pipe.execute()
    if count > settings.DEMO_MESSAGES_PER_SCENE_PER_DAY:
        raise TooManyRequests429("这个场景今天的体验次数已用完，请明天再来")
