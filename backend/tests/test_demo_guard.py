"""临时账号写保护：默认拒绝、白名单放行、开关关闭 / 读请求 / 无凭证 / 坏凭证放行。用户查询用替身。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import AppUnauthorizedFailed
from app.core.security import create_access_token
from app.services.demo import guard as module

P = settings.API_PREFIX


def req(method, route):
    return SimpleNamespace(method=method, scope={"route": SimpleNamespace(path=route)})


def creds(token):
    return SimpleNamespace(credentials=token)


@pytest.fixture
def lookups(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_ENABLED", True)
    state = {"is_guest": True, "calls": 0}

    class Q:
        def first(self):
            return self

        async def values_list(self, *a, **k):
            state["calls"] += 1
            return state["is_guest"]

    monkeypatch.setattr(module.User, "filter", lambda **k: Q())
    return state


TOKEN = create_access_token({"sub": str(uuid4())})


async def test_guest_blocked_on_management_write(lookups):
    with pytest.raises(AppUnauthorizedFailed):
        await module.guest_write_guard(req("POST", f"{P}/knowledge-bases"), creds(TOKEN))


async def test_member_passes_management_write(lookups):
    lookups["is_guest"] = False
    await module.guest_write_guard(req("DELETE", f"{P}/workspaces/{{workspace_id}}"), creds(TOKEN))


async def test_allowlisted_conversation_write_skips_lookup(lookups):
    await module.guest_write_guard(
        req("POST", f"{P}/agents/{{agent_id}}/conversations/{{conversation_id}}/stream"), creds(TOKEN)
    )
    assert lookups["calls"] == 0


@pytest.mark.parametrize("case", ["disabled", "read", "no_token", "bad_token"])
async def test_passthrough_cases(lookups, monkeypatch, case):
    route = f"{P}/knowledge-bases"
    if case == "disabled":
        monkeypatch.setattr(settings, "DEMO_ENABLED", False)
        await module.guest_write_guard(req("POST", route), creds(TOKEN))
    elif case == "read":
        await module.guest_write_guard(req("GET", route), creds(TOKEN))
    elif case == "no_token":
        await module.guest_write_guard(req("POST", route), None)
    else:
        await module.guest_write_guard(req("POST", route), creds("garbage"))
    assert lookups["calls"] == 0
