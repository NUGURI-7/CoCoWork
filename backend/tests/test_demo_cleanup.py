"""临时账号清理：先删存储再删账号、只挑过期的临时账号、存储失败时账号保留。数据库与存储用替身。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.demo import cleanup as module


class FakeUser:
    def __init__(self, log):
        self.id = uuid4()
        self._log = log

    async def delete(self):
        self._log.append(("delete_user", self.id))


@pytest.fixture
def env(monkeypatch):
    log, captured = [], {}
    ws_id = uuid4()

    class UserQ:
        def __init__(self, **kw):
            captured.update(kw)

        def limit(self, n):
            captured["limit"] = n
            return self

        def __await__(self):
            async def rows():
                return captured["rows"]
            return rows().__await__()

    class WsQ:
        def values_list(self, *a, **k):
            async def ids():
                return [ws_id]
            return ids()

    async def delete_prefix(prefix):
        if captured.get("storage_fails"):
            raise RuntimeError("R2 down")
        log.append(("delete_prefix", prefix))

    monkeypatch.setattr(module.User, "filter", lambda **kw: UserQ(**kw))
    monkeypatch.setattr(module.Workspace, "filter", lambda **kw: WsQ())
    monkeypatch.setattr(module, "storage", SimpleNamespace(delete_prefix=delete_prefix))
    return SimpleNamespace(log=log, captured=captured, ws_id=ws_id)


async def test_storage_before_account(env):
    guest = FakeUser(env.log)
    env.captured["rows"] = [guest]

    assert await module.purge_expired_guests() == 1
    assert env.log == [
        ("delete_prefix", f"sandbox/{guest.id}/"),
        ("delete_prefix", f"sandbox/{env.ws_id}/"),
        ("delete_user", guest.id),
    ]
    assert env.captured["is_guest"] is True and "created_at__lt" in env.captured
    assert env.captured["limit"] == module.PURGE_BATCH


async def test_storage_failure_keeps_account(env):
    guest = FakeUser(env.log)
    env.captured.update(rows=[guest], storage_fails=True)
    with pytest.raises(RuntimeError):
        await module.purge_expired_guests()
    assert ("delete_user", guest.id) not in env.log
