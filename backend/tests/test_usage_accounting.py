"""层 B 压缩判据的 usage 记账链路单测 —— 合成事件流,零 LLM 调用。

链路两端各测一头:
- adapter: on_chat_model_end 把 output 上的 usage_metadata 翻成 message_delta,
  且**只在主道发**(子 agent 的上下文是本轮临时的,归层 A 管,混进来会污染判据)
- collector: 一轮里主道调好几次模型、各报一份 usage,桶取**最后一次**
  (覆盖写)——它含本轮全部工具往返,而工具结果要全量进下一轮历史

取最后一次这个选择绑死在回放协议上(见 docs/design/history-replay-v1.md)。
协议若改回「工具结果不进历史」,test_collector_keeps_the_last_usage 会是第一个
提醒你改判据的地方。
"""
from langchain_core.messages import AIMessage

from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.collector import MessageCollector
from app.agents.runtime.events import EventType

# 一轮里三次模型调用的 input_tokens：进场干净 → 堆了工具往返 → 本轮峰值
FIRST_CALL_TOKENS = 8_000
MIDDLE_CALL_TOKENS = 31_000
LAST_CALL_TOKENS = 140_000


async def _stream(events: list[dict]):
    for ev in events:
        yield ev


def _model_end(meta: dict, input_tokens: int | None) -> dict:
    """一次模型调用的收尾事件；input_tokens=None 模拟 provider 不报 usage。"""
    usage = (
        None if input_tokens is None
        else {
            "input_tokens": input_tokens,
            "output_tokens": 100,
            "total_tokens": input_tokens + 100,
        }
    )
    return {
        "event": "on_chat_model_end",
        "metadata": meta,
        "data": {"output": AIMessage(content="", usage_metadata=usage)},
    }


def _usage_payloads(out: list[tuple]) -> list[dict]:
    return [payload for etype, payload in out if etype == EventType.MESSAGE_DELTA]


# ============ adapter：谁该发 usage ============


async def test_adapter_emits_usage_on_main_lane():
    """主道模型调用结束 → 发一帧 message_delta(usage)。"""
    events = [_model_end({}, FIRST_CALL_TOKENS)]
    out = [e async for e in adapt_chat_stream(_stream(events))]

    payloads = _usage_payloads(out)
    assert len(payloads) == 1
    assert payloads[0]["usage"]["input_tokens"] == FIRST_CALL_TOKENS


async def test_adapter_stays_silent_on_subagent_lane():
    """子道一帧都不许发 —— 对照组，证明拦的是泳道而非所有 usage。

    ns 带 tools: 段 = 一次 task 派发衍生的子 agent 事件（见 _lane_key）。
    """
    events = [
        _model_end({"langgraph_checkpoint_ns": "tools:0199-abcd"}, LAST_CALL_TOKENS),
    ]
    out = [e async for e in adapt_chat_stream(_stream(events))]

    assert _usage_payloads(out) == []


async def test_adapter_skips_when_provider_reports_nothing():
    """provider 不报 usage（未开 stream_usage 的兼容端点）→ 不发、不炸。"""
    events = [_model_end({}, None)]
    out = [e async for e in adapt_chat_stream(_stream(events))]

    assert _usage_payloads(out) == []


# ============ collector：留哪一次 ============


async def test_collector_keeps_the_last_usage():
    """一轮三次调用 → 桶里剩最后一次（覆盖写）。

    改回放协议时这条会先红：届时工具结果不再进历史，最后一次虚高十几倍，
    判据要改成只认第一次。
    """
    collector = MessageCollector()
    for tokens in (FIRST_CALL_TOKENS, MIDDLE_CALL_TOKENS, LAST_CALL_TOKENS):
        collector.feed(EventType.MESSAGE_DELTA, {"usage": {"input_tokens": tokens}})

    assert collector.context_tokens == LAST_CALL_TOKENS


async def test_collector_ignores_empty_usage():
    """空 / 缺字段 / 非法值一律不覆盖已有值 —— 判据宁可过时，不可被清零。

    清零 = 判据永远不超线 = 层 B 再也不触发，比一个过时的近似值糟得多。
    """
    collector = MessageCollector()
    collector.feed(EventType.MESSAGE_DELTA, {"usage": {"input_tokens": LAST_CALL_TOKENS}})

    for junk in ({}, {"usage": {}}, {"usage": {"input_tokens": 0}}, {"usage": None}):
        collector.feed(EventType.MESSAGE_DELTA, junk)

    assert collector.context_tokens == LAST_CALL_TOKENS


async def test_collector_leaves_usage_out_of_message_content():
    """usage 落 Conversation，不该混进 Message.content 的块列表。"""
    collector = MessageCollector()
    collector.feed(EventType.MESSAGE_DELTA, {"usage": {"input_tokens": FIRST_CALL_TOKENS}})

    assert collector.blocks == []
