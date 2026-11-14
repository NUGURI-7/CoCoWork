"""体验场景解析：场景表查不到、单 Agent 直达、工作空间走复制。复制本身要真库，这里只测分派。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import DemoScene, settings
from app.core.exceptions import Conflict409, NotFound404
from app.services.demo import scene_service as module

USER = SimpleNamespace(id=uuid4())


async def test_unknown_scene_is_404(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_SCENES", {})
    with pytest.raises(NotFound404):
        await module.resolve_scene(USER, "nope")


async def test_agent_scene_returns_agent_id(monkeypatch):
    agent_id = uuid4()
    checked = []

    async def usable(user, aid):
        checked.append((user, aid))

    monkeypatch.setattr(settings, "DEMO_SCENES", {"audio": DemoScene(kind="agent", target_id=agent_id)})
    monkeypatch.setattr(module, "get_usable_agent", usable)

    entry = await module.resolve_scene(USER, "audio")
    assert (entry.kind, entry.target_id) == ("agent", agent_id)
    assert checked == [(USER, agent_id)]


async def test_offline_agent_propagates_409(monkeypatch):
    async def offline(user, aid):
        raise Conflict409("该 Agent 已下线")

    monkeypatch.setattr(settings, "DEMO_SCENES", {"audio": DemoScene(kind="agent", target_id=uuid4())})
    monkeypatch.setattr(module, "get_usable_agent", offline)
    with pytest.raises(Conflict409):
        await module.resolve_scene(USER, "audio")


async def test_workspace_scene_returns_copy_id(monkeypatch):
    template_id, copy_id = uuid4(), uuid4()

    async def copy(user, tid):
        assert (user, tid) == (USER, template_id)
        return SimpleNamespace(id=copy_id)

    monkeypatch.setattr(settings, "DEMO_SCENES", {"doc": DemoScene(kind="workspace", target_id=template_id)})
    monkeypatch.setattr(module, "ensure_workspace_copy", copy)

    entry = await module.resolve_scene(USER, "doc")
    assert (entry.kind, entry.target_id) == ("workspace", copy_id)
