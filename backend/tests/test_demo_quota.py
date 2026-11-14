"""体验限额：正式用户放行、字数上限、每人每场景次数、检查顺序。Token 汇总查询用替身。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import TooManyRequests429, ValidationException
from app.services.demo import quota as module
from tests.test_guest_service import FakeRedis

GUEST = SimpleNamespace(id=uuid4(), is_guest=True)
MEMBER = SimpleNamespace(id=uuid4(), is_guest=False)


class FakeRequest:
    def __init__(self, text="你好", path_params=None, raw=None):
        self.path_params = path_params or {"agent_id": "a1"}
        self._body = raw if raw is not None else {"content": [{"type": "text", "text": text}]}

    async def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.fixture
def budget(monkeypatch):
    calls = []

    async def ok():
        calls.append(1)

    monkeypatch.setattr(module, "_ensure_token_budget", ok)
    return calls


async def test_member_is_not_limited(budget):
    redis = FakeRedis()
    await module.guest_send_quota(FakeRequest(text="x" * 99999), MEMBER, redis)
    assert redis.store == {} and budget == []


async def test_too_long_rejected_before_counting(budget):
    redis = FakeRedis()
    with pytest.raises(ValidationException):
        await module.guest_send_quota(FakeRequest(text="x" * (settings.DEMO_MAX_INPUT_CHARS + 1)), GUEST, redis)
    assert redis.store == {} and budget == []


async def test_scene_limit_per_target(budget, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MESSAGES_PER_SCENE_PER_DAY", 2)
    redis = FakeRedis()
    audio = FakeRequest(path_params={"agent_id": "audio"})
    for _ in range(2):
        await module.guest_send_quota(audio, GUEST, redis)
    with pytest.raises(TooManyRequests429):
        await module.guest_send_quota(audio, GUEST, redis)
    await module.guest_send_quota(FakeRequest(path_params={"workspace_id": "ws"}), GUEST, redis)


async def test_budget_exhausted_does_not_consume_count(monkeypatch):
    async def exhausted():
        raise TooManyRequests429("今天的体验额度已用完，请明天再来")

    monkeypatch.setattr(module, "_ensure_token_budget", exhausted)
    redis = FakeRedis()
    with pytest.raises(TooManyRequests429):
        await module.guest_send_quota(FakeRequest(), GUEST, redis)
    assert redis.store == {}


async def test_malformed_body_left_to_endpoint(budget):
    await module.guest_send_quota(FakeRequest(raw=ValueError("bad json")), GUEST, FakeRedis())


async def test_resume_only_checks_budget(budget):
    await module.guest_token_budget(GUEST)
    await module.guest_token_budget(MEMBER)
    assert budget == [1]


async def test_remaining_tracks_consumed(budget, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MESSAGES_PER_SCENE_PER_DAY", 3)

    class GetRedis(FakeRedis):
        async def get(self, key):
            return self.store.get(key)

    redis = GetRedis()
    assert await module.remaining_scene_messages(redis, GUEST, "audio") == 3
    await module.guest_send_quota(FakeRequest(path_params={"agent_id": "audio"}), GUEST, redis)
    assert await module.remaining_scene_messages(redis, GUEST, "audio") == 2
    assert await module.remaining_scene_messages(redis, GUEST, "ws") == 3
    redis.store = {k: 99 for k in redis.store}
    assert await module.remaining_scene_messages(redis, GUEST, "audio") == 0
