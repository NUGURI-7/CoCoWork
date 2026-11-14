"""官网免登录体验：给每位访客建一个临时账号并签发凭证。"""

import secrets
from datetime import date, timedelta

from fastapi import Depends
from redis import asyncio as aioredis

from app.core.config import settings
from app.core.exceptions import TooManyRequests429
from app.core.redis import get_redis
from app.core.security import create_access_token, get_password_hash
from app.models.user import User

SECONDS_PER_DAY = 24 * 60 * 60


class GuestService:
    def __init__(self, redis: aioredis.Redis):
        self._redis = redis

    async def sign_in(self, client_ip: str) -> dict:
        await self._consume_signup_quota(client_ip)
        user = await self._create_guest()
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.DEMO_TOKEN_EXPIRE_MINUTES),
        )
        return {"access_token": access_token, "user": user}

    async def _consume_signup_quota(self, client_ip: str) -> None:
        key = f"demo:signup:{date.today().isoformat()}:{client_ip}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, SECONDS_PER_DAY, nx=True)
            count, _ = await pipe.execute()
        if count > settings.DEMO_GUESTS_PER_IP_PER_DAY:
            raise TooManyRequests429("今天的体验次数已用完，请明天再来")

    async def _create_guest(self) -> User:
        username = f"guest_{secrets.token_hex(6)}"
        return await User.create(
            username=username,
            email=f"{username}@guest.invalid",
            password_hash=get_password_hash(secrets.token_urlsafe(32)),
            nick_name="体验访客",
            is_guest=True,
        )


async def get_guest_service(redis: aioredis.Redis = Depends(get_redis)) -> GuestService:
    return GuestService(redis)
