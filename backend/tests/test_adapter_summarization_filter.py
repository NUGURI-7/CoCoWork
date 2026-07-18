"""adapter 摘要事件过滤单测 —— 合成事件流,零 LLM 调用。

摘要中间件的内部调用带 metadata.lc_source == "summarization"(dump 实证),
adapter 主循环应把这类事件整体拦下;同形态的正常事件必须原样通过(对照组)。
"""
from langchain_core.messages import AIMessageChunk

from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.events import EventType


async def _stream(events: list[dict]):
    for ev in events:
        yield ev


def _chat_model_events(meta: dict) -> list[dict]:
    """一段最小的模型调用事件序列:start → 吐一个 token → end。"""
    chunk = AIMessageChunk(content="## SUMMARY 张三住杭州")
    return [
        {"event": "on_chat_model_start", "metadata": meta, "data": {}},
        {"event": "on_chat_model_stream", "metadata": meta, "data": {"chunk": chunk}},
        {"event": "on_chat_model_end", "metadata": meta, "data": {}},
    ]


async def test_summarization_events_are_dropped():
    """带摘要戳的事件一个都不许漏出去。"""
    events = _chat_model_events({"lc_source": "summarization"})
    out = [e async for e in adapt_chat_stream(_stream(events))]
    assert out == []


async def test_normal_events_pass_through():
    """无戳的同形态事件正常翻译 —— 证明拦的是戳,不是误伤所有事件。"""
    events = _chat_model_events({})
    out = [e async for e in adapt_chat_stream(_stream(events))]
    deltas = [payload for etype, payload in out if etype == EventType.CONTENT_BLOCK_DELTA]
    assert any("张三" in str(p) for p in deltas), "正文 token 应该穿过 adapter"
