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
