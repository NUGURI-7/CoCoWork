"""运行时资源可用规则：查询条件的形状、内置 Skill 密钥「自己的覆盖管理员的」。"""

import json
from types import SimpleNamespace
from uuid import uuid4

from app.services.access import usable_by
from app.services.skill import builtin as module

USER = SimpleNamespace(id=uuid4())


def test_usable_by_is_owner_or_admin():
    q = usable_by(USER)
    assert q.join_type == "OR"
    assert [c.filters for c in q.children] == [{"created_by": USER}, {"created_by__is_admin": True}]


def test_usable_by_follows_owner_path():
    q = usable_by(USER, owner="provider__created_by")
    assert [c.filters for c in q.children] == [
        {"provider__created_by": USER},
        {"provider__created_by__is_admin": True},
    ]


async def test_own_credentials_override_admin(monkeypatch):
    admin_id = uuid4()
    rows = [
        SimpleNamespace(created_by_id=USER.id, credentials_encrypted=json.dumps({"TTS_KEY": "mine"})),
        SimpleNamespace(created_by_id=admin_id, credentials_encrypted=json.dumps({"TTS_KEY": "admin", "MAP_KEY": "a"})),
    ]

    class FakeQuery:
        def __await__(self):
            async def done():
                return rows
            return done().__await__()

    monkeypatch.setattr(module.Skill, "filter", lambda *a, **k: FakeQuery())
    monkeypatch.setattr(module, "decrypt", lambda s: s)

    env = await module.fetch_builtin_credentials(USER, ["tts", "map"])
    assert env == {"TTS_KEY": "mine", "MAP_KEY": "a"}
