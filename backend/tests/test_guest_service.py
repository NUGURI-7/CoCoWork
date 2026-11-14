"""体验访客建号：按 IP 每天限次、临时账号的字段、凭证有效期。Redis 与数据库用替身。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.exceptions import TooManyRequests429
from app.services.demo import guest_service as module
from app.services.demo.guest_service import SECONDS_PER_DAY, GuestService


class FakePipeline:
    def __init__(self, store: dict, ttls: dict):
        self._store, self._ttls, self._ops = store, ttls, []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def incr(self, key):
        self._ops.append(("incr", key))

    def expire(self, key, seconds, nx=False):
        self._ops.append(("expire", key, seconds, nx))

    async def execute(self):
        results = []
        for op in self._ops:
            if op[0] == "incr":
                self._store[op[1]] = self._store.get(op[1], 0) + 1
                results.append(self._store[op[1]])
            else:
                _, key, seconds, nx = op
                if not (nx and key in self._ttls):
                    self._ttls[key] = seconds
                results.append(True)
        return results


class FakeRedis:
    def __init__(self):
        self.store, self.ttls = {}, {}

    def pipeline(self, transaction=True):
        return FakePipeline(self.store, self.ttls)


@pytest.fixture
def created(monkeypatch):
    rows = []

    async def fake_create(**kwargs):
        user = SimpleNamespace(id=uuid4(), **kwargs)
        rows.append(user)
        return user

    monkeypatch.setattr(module.User, "create", fake_create)
    return rows


async def test_creates_guest_and_long_lived_token(created):
    result = await GuestService(FakeRedis()).sign_in("1.2.3.4")

    user = created[0]
    assert user.is_guest is True
    assert user.username.startswith("guest_") and len(user.username) <= 20
    assert user.email == f"{user.username}@guest.nuguri.org"
    assert result["user"] is user

    payload = jwt.decode(result["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == str(user.id)
    lifetime = payload["exp"] - int(datetime.now(timezone.utc).timestamp())
    assert abs(lifetime - settings.DEMO_TOKEN_EXPIRE_MINUTES * 60) < 5


async def test_rejects_after_daily_limit_per_ip(created, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_GUESTS_PER_IP_PER_DAY", 2)
    svc = GuestService(FakeRedis())

    await svc.sign_in("1.2.3.4")
    await svc.sign_in("1.2.3.4")
    with pytest.raises(TooManyRequests429):
        await svc.sign_in("1.2.3.4")
    assert len(created) == 2

    await svc.sign_in("5.6.7.8")
    assert len(created) == 3


async def test_window_expiry_set_once(created):
    redis = FakeRedis()
    svc = GuestService(redis)
    await svc.sign_in("1.2.3.4")
    redis.ttls = {k: 1 for k in redis.ttls}
    await svc.sign_in("1.2.3.4")
    assert list(redis.ttls.values()) == [1]
    assert SECONDS_PER_DAY == 86400
