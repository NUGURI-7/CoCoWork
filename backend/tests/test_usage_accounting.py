"""usage 记账链路单测 —— 合成事件流,零 LLM 调用。

一条链路两笔账,各测各的:
- **上下文规模**(层 B 压缩判据):只认主道、取最后一次(覆盖写)——它含本轮全部
  工具往返,而工具结果要全量进下一轮历史
- **本轮总消耗**(展示给用户):主道 + 子道全收、跨调用累加,按 delegate_id 分行

adapter 两道都发 usage,子道那帧带 delegate_id 戳;分流在 collector 做。

取最后一次这个选择绑死在回放协议上(见 docs/design/history-replay-v1.md)。
协议若改回「工具结果不进历史」,test_collector_keeps_the_last_usage 会是第一个
提醒你改判据的地方。
"""
import json

from langchain_core.messages import AIMessage, AIMessageChunk
from uuid_utils import compat as uuid_compat

from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.collector import MessageCollector
from app.agents.runtime.events import EventType
from app.agents.runtime.runner import run_chat_stream

# 一轮里三次模型调用的 input_tokens：进场干净 → 堆了工具往返 → 本轮峰值
FIRST_CALL_TOKENS = 8_000
MIDDLE_CALL_TOKENS = 31_000
LAST_CALL_TOKENS = 140_000

# 一次派活：task 工具的 tool_call_id + 它衍生出的子泳道 ns
DELEGATE_CALL_ID = "call_delegate_0"
SUB_LANE_NS = "tools:0199-abcd"


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


def _task_call_chunk() -> dict:
    """supervisor 吐出 task 工具调用 —— adapter 据此记下「第 0 个 task → call_id」。"""
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{
            "name": "task",
            "args": "",
            "id": DELEGATE_CALL_ID,
            "index": 0,
            "type": "tool_call_chunk",
        }],
    )
    return {"event": "on_chat_model_stream", "metadata": {}, "data": {"chunk": chunk}}


def _task_started() -> dict:
    """task 开跑 —— adapter 据此把子泳道绑定到这次派活（lane_to_delegate）。

    langgraph_path 里的 0 = 这是 supervisor 派的第 0 个 task，跟上面的 chunk index 对上。
    """
    return {
        "event": "on_tool_start",
        "name": "task",
        "metadata": {
            "langgraph_checkpoint_ns": SUB_LANE_NS,
            "langgraph_path": ["__pregel_push", 0, False],
        },
        "data": {},
    }


def _usage_payloads(out: list[tuple]) -> list[dict]:
    return [payload for etype, payload in out if etype == EventType.MESSAGE_DELTA]


def _feed_usage(
        collector: MessageCollector,
        input_tokens: int,
        output_tokens: int = 0,
        delegate_id: str | None = None,
) -> None:
    """喂一帧 message_delta；delegate_id=None 即主道。"""
    payload: dict = {
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    if delegate_id is not None:
        payload["delegate_id"] = delegate_id
    collector.feed(EventType.MESSAGE_DELTA, payload)


# ============ adapter：谁该发 usage ============


async def test_adapter_emits_usage_on_main_lane():
    """主道模型调用结束 → 发一帧 message_delta(usage)，不带 delegate_id。"""
    events = [_model_end({}, FIRST_CALL_TOKENS)]
    out = [e async for e in adapt_chat_stream(_stream(events))]

    payloads = _usage_payloads(out)
    assert len(payloads) == 1
    assert payloads[0]["usage"]["input_tokens"] == FIRST_CALL_TOKENS
    assert "delegate_id" not in payloads[0]


async def test_adapter_emits_usage_on_subagent_lane_with_stamp():
    """子道也发 usage，且带 delegate_id 戳 —— 总消耗要算上成员烧的 token。

    戳是下游分账的唯一判据（主道没有这个字段），所以这里连「发了」和「带戳」
    一起锁死：少了戳，子 agent 的数字会被当成 supervisor 的算进层 B 判据。
    """
    events = [
        _task_call_chunk(),
        _task_started(),
        _model_end({"langgraph_checkpoint_ns": SUB_LANE_NS}, LAST_CALL_TOKENS),
    ]
    out = [e async for e in adapt_chat_stream(_stream(events))]

    payloads = _usage_payloads(out)
    assert len(payloads) == 1
    assert payloads[0]["usage"]["input_tokens"] == LAST_CALL_TOKENS
    assert payloads[0]["delegate_id"] == DELEGATE_CALL_ID


async def test_adapter_skips_when_provider_reports_nothing():
    """provider 不报 usage（未开 stream_usage 的兼容端点）→ 不发、不炸。"""
    events = [_model_end({}, None)]
    out = [e async for e in adapt_chat_stream(_stream(events))]

    assert _usage_payloads(out) == []


# ============ collector · 上下文规模：留哪一次 ============


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


async def test_collector_keeps_subagent_usage_out_of_context_size():
    """子道的 usage 不许进层 B 判据 —— 闸门放开后最容易坏的就是这条。

    子 agent 的上下文本轮临时、run 完即弃，跟对话历史规模无关；它若最后到，
    覆盖写就会把判据换成子 agent 的上下文长度，压缩时机整体跑偏。
    """
    collector = MessageCollector()
    _feed_usage(collector, MIDDLE_CALL_TOKENS)
    _feed_usage(collector, LAST_CALL_TOKENS, delegate_id=DELEGATE_CALL_ID)

    assert collector.context_tokens == MIDDLE_CALL_TOKENS


async def test_collector_leaves_usage_out_of_message_content():
    """usage 落 Conversation / Message 的列，不该混进 content 的块列表。"""
    collector = MessageCollector()
    collector.feed(EventType.MESSAGE_DELTA, {"usage": {"input_tokens": FIRST_CALL_TOKENS}})

    assert collector.blocks == []


# ============ collector · 总消耗：怎么累加、怎么分行 ============


async def test_collector_accumulates_across_calls():
    """同一行内跨调用累加，不是覆盖 —— 模型每次都真读了那么多。"""
    collector = MessageCollector()
    _feed_usage(collector, FIRST_CALL_TOKENS, output_tokens=100)
    _feed_usage(collector, MIDDLE_CALL_TOKENS, output_tokens=200)

    assert collector.prompt_tokens == FIRST_CALL_TOKENS + MIDDLE_CALL_TOKENS
    assert collector.completion_tokens == 300
    assert collector.usage_rows == [
        {
            "delegate_id": None,
            "prompt_tokens": FIRST_CALL_TOKENS + MIDDLE_CALL_TOKENS,
            "completion_tokens": 300,
        },
    ]


async def test_collector_totals_include_subagents():
    """合计 = supervisor + 全部子 agent，明细按行拆开。"""
    collector = MessageCollector()
    _feed_usage(collector, FIRST_CALL_TOKENS, output_tokens=100)
    _feed_usage(collector, MIDDLE_CALL_TOKENS, output_tokens=200, delegate_id=DELEGATE_CALL_ID)

    assert collector.prompt_tokens == FIRST_CALL_TOKENS + MIDDLE_CALL_TOKENS
    assert collector.completion_tokens == 300
    assert collector.usage_rows == [
        {"delegate_id": None, "prompt_tokens": FIRST_CALL_TOKENS, "completion_tokens": 100},
        {
            "delegate_id": DELEGATE_CALL_ID,
            "prompt_tokens": MIDDLE_CALL_TOKENS,
            "completion_tokens": 200,
        },
    ]


async def test_collector_splits_concurrent_delegations_of_same_member():
    """同一个成员被并发派两次 = 两行，不合并。

    分行的单位是「一次派活」而非「一个成员」：合并了就看不出哪次贵，
    定位能力直接没了。delegate_id 每次派发独立生成，天然就是两个。
    """
    collector = MessageCollector()
    _feed_usage(collector, 1_000, output_tokens=10, delegate_id="call_a")
    _feed_usage(collector, 2_000, output_tokens=20, delegate_id="call_b")
    _feed_usage(collector, 3_000, output_tokens=30, delegate_id="call_a")

    assert collector.usage_rows == [
        {"delegate_id": "call_a", "prompt_tokens": 4_000, "completion_tokens": 40},
        {"delegate_id": "call_b", "prompt_tokens": 2_000, "completion_tokens": 20},
    ]


async def test_collector_summary_mirrors_the_db_columns():
    """usage_summary 的三个键 == messages 表新增的三列,SSE 与落库同源同形。"""
    collector = MessageCollector()
    _feed_usage(collector, FIRST_CALL_TOKENS, output_tokens=100)

    assert collector.usage_summary == {
        "prompt_tokens": FIRST_CALL_TOKENS,
        "completion_tokens": 100,
        "token_usage": [
            {"delegate_id": None, "prompt_tokens": FIRST_CALL_TOKENS, "completion_tokens": 100},
        ],
    }


async def test_collector_rejects_junk_token_values():
    """非 int / 负数 / bool 一律当 0，且不开出空行 —— 热路径上不许炸。"""
    collector = MessageCollector()
    for junk in (None, "8000", -5, True):
        _feed_usage(collector, junk, output_tokens=junk, delegate_id="call_junk")  # type: ignore[arg-type]

    assert collector.usage_rows == []
    assert collector.prompt_tokens == 0


# ============ runner：终止帧捎汇总 ============


class _FakeGraph:
    """只提供 astream_events 的最小图 —— runner 用不到别的。"""

    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def astream_events(self, *_args, **_kwargs):
        return _stream(self._events)


def _stop_frame(sse_chunks: list[str]) -> dict:
    """从 SSE 帧串里捡出 message_stop 的 data。"""
    for chunk in sse_chunks:
        if chunk.startswith(f"event: {EventType.MESSAGE_STOP}\n"):
            return json.loads(chunk.split("data: ", 1)[1])
    raise AssertionError("没发 message_stop")


async def test_stop_frame_carries_the_summary_collected_during_the_stream():
    """终止帧带的是**流跑完后**的汇总 —— 也就是那个 lambda 确实被延后兑现了。

    回调若在 run_chat_stream 调用那一刻就求值,桶还是空的,这里会全 0。
    """
    collector = MessageCollector()
    graph = _FakeGraph([
        _model_end({}, FIRST_CALL_TOKENS),
        _task_call_chunk(),
        _task_started(),
        _model_end({"langgraph_checkpoint_ns": SUB_LANE_NS}, MIDDLE_CALL_TOKENS),
    ])

    chunks = [
        c async for c in run_chat_stream(
            graph,  # type: ignore[arg-type]
            [],
            message_id=uuid_compat.uuid7(),
            sink=collector.feed,
            usage=lambda: collector.usage_summary,
        )
    ]

    stop = _stop_frame(chunks)
    assert stop["prompt_tokens"] == FIRST_CALL_TOKENS + MIDDLE_CALL_TOKENS
    assert stop["completion_tokens"] == 200
    assert [row["delegate_id"] for row in stop["token_usage"]] == [None, DELEGATE_CALL_ID]


async def test_stop_frame_still_goes_out_when_the_summary_blows_up():
    """汇总炸了不许连累 message_stop —— 前端靠它关活气泡,没有就一直转圈。"""
    def boom() -> dict:
        raise RuntimeError("汇总炸了")

    chunks = [
        c async for c in run_chat_stream(
            _FakeGraph([]),  # type: ignore[arg-type]
            [],
            message_id=uuid_compat.uuid7(),
            usage=boom,
        )
    ]

    assert set(_stop_frame(chunks)) == {"id"}  # 帧照发,只是不带汇总
