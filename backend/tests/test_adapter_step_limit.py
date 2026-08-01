"""撞到步数上限时的收尾 —— 合成事件流，零 LLM 调用。

`RECURSION_LIMIT` 那道保护生效时，LangGraph 抛 `GraphRecursionError`。它继承
`RecursionError → RuntimeError → Exception`，所以在加专门分支之前，会掉进 adapter
兜底的 `except Exception` 里，跟真 bug 一样吐通用文案「对话生成失败，请稍后重试」。

这组测试锁住三件事：已产出的内容不丢、文案说的是「没做完」而不是「失败」、
以及真异常仍然走通用分支（证明拦的是这一类异常，不是把所有异常都改口了）。
"""

from langchain_core.messages import AIMessageChunk
from langgraph.errors import GraphRecursionError

from app.agents.runtime.adapter import (
    ERROR_CODE_INTERNAL,
    ERROR_CODE_STEP_LIMIT,
    ERROR_MESSAGE_GENERIC,
    ERROR_MESSAGE_STEP_LIMIT,
    adapt_chat_stream,
)
from app.agents.runtime.events import EventType


async def _stream_then_raise(exc: Exception):
    """先正常吐半句话，再抛异常 —— 模拟「做到一半撞上限」。"""
    meta: dict = {}
    yield {"event": "on_chat_model_start", "metadata": meta, "data": {}}
    yield {
        "event": "on_chat_model_stream",
        "metadata": meta,
        "data": {"chunk": AIMessageChunk(content="第一步我先查了报销制度")},
    }
    raise exc


def _errors(out: list) -> list[dict]:
    return [p for etype, p in out if etype == EventType.ERROR]


async def test_步数上限走专门文案而非通用错误():
    out = [e async for e in adapt_chat_stream(_stream_then_raise(GraphRecursionError()))]

    errors = _errors(out)
    assert len(errors) == 1
    assert errors[0]["code"] == ERROR_CODE_STEP_LIMIT
    assert errors[0]["message"] == ERROR_MESSAGE_STEP_LIMIT
    # 「失败请重试」是误导：重试解决不了，前面做的东西还在
    assert ERROR_MESSAGE_GENERIC not in errors[0]["message"]


async def test_已产出的内容不丢且块被关掉():
    """撞上限时正开着一个 text 块 —— 内容要留住，块要关掉，否则前端光标卡着。"""
    out = [e async for e in adapt_chat_stream(_stream_then_raise(GraphRecursionError()))]

    deltas = [p for etype, p in out if etype == EventType.CONTENT_BLOCK_DELTA]
    assert any("报销制度" in str(p) for p in deltas), "撞上限前产出的正文必须留住"

    stops = [p for etype, p in out if etype == EventType.CONTENT_BLOCK_STOP]
    assert stops, "开着的块必须被关掉"

    # 顺序要紧：先关块，再报错。反过来前端会先渲染错误、再收到孤儿 stop
    kinds = [etype for etype, _ in out]
    assert kinds.index(EventType.CONTENT_BLOCK_STOP) < kinds.index(EventType.ERROR)


async def test_真异常仍走通用分支():
    """对照组：拦的是步数上限这一类，不是把所有异常都改了口。"""
    out = [e async for e in adapt_chat_stream(_stream_then_raise(ValueError("boom")))]

    errors = _errors(out)
    assert len(errors) == 1
    assert errors[0]["code"] == ERROR_CODE_INTERNAL
    assert errors[0]["message"] == ERROR_MESSAGE_GENERIC
    # 原始异常信息不能外泄给前端
    assert "boom" not in errors[0]["message"]


async def test_递归上限是我们自己定的值():
    """不是框架默认的 25 —— 这条测试的意义是「有人动了这个数会被叫住」。"""
    from app.agents.runtime.runner import RECURSION_LIMIT

    assert RECURSION_LIMIT == 40
    assert RECURSION_LIMIT > 25, "低于框架默认值就失去了显式设置的意义"
