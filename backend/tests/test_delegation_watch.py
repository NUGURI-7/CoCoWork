"""认出「成员交活」的时机：只认 supervisor 派活的 task 调用拿到结果。"""

from app.agents.runtime.events import EventType
from app.agents.runtime.runner import _DelegationWatch


def test_派活结果到达时认作交活且只认一次():
    w = _DelegationWatch()
    assert not w.finished(EventType.TOOL_USE_START, {"id": "t1", "name": "task"})
    assert w.finished(EventType.TOOL_RESULT, {"id": "t1"})
    assert not w.finished(EventType.TOOL_RESULT, {"id": "t1"})


def test_成员内部的工具不算交活():
    w = _DelegationWatch()
    w.finished(EventType.TOOL_USE_START, {"id": "t1", "name": "task"})
    w.finished(EventType.TOOL_USE_START, {"id": "x1", "name": "execute", "delegate_id": "t1"})
    assert not w.finished(EventType.TOOL_RESULT, {"id": "x1", "delegate_id": "t1"})


def test_其他工具和无关事件不算交活():
    w = _DelegationWatch()
    w.finished(EventType.TOOL_USE_START, {"id": "k1", "name": "knowledge_search"})
    assert not w.finished(EventType.TOOL_RESULT, {"id": "k1"})
    assert not w.finished(EventType.TOOL_RESULT, {"id": "unknown"})


def test_并行派出的多个成员各自交活():
    w = _DelegationWatch()
    for cid in ("a", "b", "c"):
        w.finished(EventType.TOOL_USE_START, {"id": cid, "name": "task"})
    assert [w.finished(EventType.TOOL_RESULT, {"id": cid}) for cid in ("b", "a", "c")] == [True, True, True]


async def test_单Agent对话的收产物函数能走推送产物帧的流程(monkeypatch):
    """回归：单 Agent 那条路的收产物函数曾不认 final 参数，收尾时报错、产物卡片推不出去。"""
    from functools import partial
    from types import SimpleNamespace
    from uuid import uuid4

    from app.agents.runtime.runner import _artifacts_payload
    from app.api.routes.agent import conversation

    message_id = uuid4()
    row = SimpleNamespace(id=uuid4(), filename="播报.mp3", size=1024, content_type="audio/mpeg")

    class _Query:
        async def _rows(self):
            return [row]

        def order_by(self, *_):
            return self._rows()

    monkeypatch.setattr(conversation.SandboxArtifact, "filter", lambda **_: _Query())

    payload = await _artifacts_payload(partial(conversation._message_artifacts, message_id), message_id, final=True)
    assert payload["artifacts"][0]["filename"] == "播报.mp3"
