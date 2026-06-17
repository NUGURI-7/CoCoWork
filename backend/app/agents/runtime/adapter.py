"""LangChain `astream_events(v2)` → 结构化事件翻译器（SSE 序列化由 runner 统一做）。

设计原则：
- 函数式 + 模块顶部常量集中（事件名 / payload key / 错误文案 / 截断长度）
- 数据结构用 dataclass 持有，复杂表用小方法保证原子性（不引入继承层次）
- 单一关块入口 `_close_open_blocks` —— 正常路径和异常兜底共用，避免漂移
- 对前端只发通用错误文案，原始异常 `logger.exception` 留给后端
- dispatch 装饰器登记 LangChain 事件 → handler；扩展新事件类型 = 新加一个 `@_register`

支持的块类型：
- text     — chunk.content（str）
- thinking — chunk.additional_kwargs.reasoning_content（DeepSeek-R1 风格）
- tool_use — chunk.tool_call_chunks（多并发按 chunk.index 区分）+ on_tool_end 发结果

外层 runner 负责 message_start / message_stop；本翻译器只产「块事件 + message_delta + tool_result」。
"""

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any
from langgraph.types import Command
from app.agents.runtime.events import EventType

logger = logging.getLogger(__name__)

# ============ 协议常量（事件名 / payload key / 配置） ============


# 块类型（content_block_start.type）
BLOCK_TEXT = "text"
BLOCK_THINKING = "thinking"

# delta 类型（content_block_delta.type / tool_use_delta.type）
DELTA_TYPE_TEXT = "text_delta"
DELTA_TYPE_THINKING = "thinking_delta"
DELTA_TYPE_INPUT_JSON = "input_json_delta"

# delta payload 的内容 key
DELTA_KEY_TEXT = "text"
DELTA_KEY_THINKING = "thinking"

# message_delta 默认 stop reason
DEFAULT_STOP_REASON = "end_turn"

# 错误事件
ERROR_CODE_INTERNAL = "internal_error"
ERROR_MESSAGE_GENERIC = "对话生成失败，请稍后重试"

# Tool 结果摘要截断长度
TOOL_SUMMARY_MAX_CHARS = 100

# Tool 调用 input_preview 默认值
TOOL_INPUT_PREVIEW_DEFAULT = ""


# ============ 状态机 ============

@dataclass
class SingletonSlot:
    """单例块槽位：一个 stream 内同类型最多一个活块（text / thinking / 未来 image）。

    index != None ⇒ 块开着；None ⇒ 没开 / 已关。纯数据持有，操作由外部 helper 完成。
    """

    index: int | None = None


@dataclass
class ToolRegistry:
    """tool 块多并发注册表 —— LangChain chunk.index ↔ 我们的 block_idx 双向 + tool_call_id 索引。

        on_tool_end 用 tool_call_id 反查 block_idx（O(1)）；_close_open_blocks 用 chunk.index 关。
        register / release 封装"多表同步"防止漂移。
    """

    chunk_to_block: dict[int, int] = field(default_factory=dict)
    id_to_block: dict[str, int] = field(default_factory=dict)
    block_to_id: dict[int, str] = field(default_factory=dict)

    def register(self, chunk_index: int, block_idx: int, tool_id: str) -> None:
        self.chunk_to_block[chunk_index] = block_idx
        self.id_to_block[tool_id] = block_idx
        self.block_to_id[block_idx] = tool_id

    def release(self, chunk_index: int) -> tuple[int, str] | None:
        """关闭某 chunk_index 对应的活块：清流式收发映射，返回 (block_idx, tool_id)。

        只清 `chunk_to_block`；`id_to_block` / `block_to_id` 留给 `on_tool_end`
        反查（它在 chat_model_end 之后才触发）。本 State 跟 SSE 流同生共死，
        流结束 GC 自动清，不会泄漏。
        """
        block_idx = self.chunk_to_block.pop(chunk_index, None)
        if block_idx is None:
            return None
        tool_id = self.block_to_id.get(block_idx, "")
        return block_idx, tool_id


@dataclass
class StreamState:
    """所有活块状态 + 全局单调编号。"""

    next_index: int = 0
    text: SingletonSlot = field(default_factory=SingletonSlot)
    thinking: SingletonSlot = field(default_factory=SingletonSlot)
    tools: ToolRegistry = field(default_factory=ToolRegistry)

    def allocate(self) -> int:
        """领一个新的块编号。"""
        idx = self.next_index
        self.next_index += 1
        return idx


# ============ Dispatch 表 ============

# adapter 对外吐的事件原料：(事件类型, payload dict)。粘成 SSE 字符串是 runner 的活。
AdapterEvent = tuple[EventType, dict[str, Any]]

Handler = Callable[[StreamState, dict[str, Any]], AsyncIterator[AdapterEvent]]
_HANDLERS: dict[str, Handler] = {}


def _register(event_name: str) -> Callable[[Handler], Handler]:
    """LangChain 事件名 → 处理函数登记装饰器。"""

    def decorator(fn: Handler) -> Handler:
        _HANDLERS[event_name] = fn
        return fn

    return decorator


# ============ chunk 字段抽取（只读、零副作用） ============

def _extract_text(chunk: Any) -> str:
    """
    从 chunk.content 抽 text 增量。

    LangChain 跨 provider 两种形态：
    - str        — Chat Completions 默认
    - list[dict] — Anthropic / Responses API / 多模态，聚合所有 type=text 的 text 字段

    list 里非 text 的 part（image / audio / reasoning）由各自专门 extractor 处理。
    """

    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _extract_reasoning(chunk: Any) -> str:
    """从 chunk 抽 thinking / reasoning 增量，跨 provider 两路聚合。

    - DeepSeek-R1 / 通义千问 QwQ：`chunk.additional_kwargs.reasoning_content` (str)
    - Anthropic extended thinking：`chunk.content` 是 list[dict]，含 {"type": "thinking", "thinking": "..."}

    都拿到就拼起来——一个 chunk 通常只会走其中一条。
    """
    parts: list[str] = []

    # 路径 1：additional_kwargs.reasoning_content（OpenAI 兼容 reasoning 模型）
    extras = getattr(chunk, "additional_kwargs", None) or {}
    val = extras.get("reasoning_content")
    if isinstance(val, str) and val:
        parts.append(val)

    # 路径 2：content list 里的 thinking 块（Anthropic extended thinking）
    content = getattr(chunk, "content", None)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "thinking":
                t = part.get("thinking")
                if isinstance(t, str):
                    parts.append(t)

    return "".join(parts)


def _tc_field(tc: Any, key: str) -> Any:
    """LangChain ToolCallChunk 运行时可能是 dict / TypedDict / 带属性对象，统一取值。"""
    return tc.get(key) if isinstance(tc, dict) else getattr(tc, key, None)


def _summarize_tool_result(content: Any) -> str:
    """tool 结果摘要（前端折叠视图用）。"""
    if isinstance(content, str):
        return content[:TOOL_SUMMARY_MAX_CHARS]
    if isinstance(content, list):
        return f"返回 {len(content)} 项结果"
    return str(content)[:TOOL_SUMMARY_MAX_CHARS]


def _unwrap_tool_output(output: Any) -> Any:
    """工具返回值归一化 —— Command 解包出内部 ToolMessage，其余原样返回。

    langgraph 工具可返回 Command 注入 state（而非直接回值），deepagents 的
    task 派活工具即此模式：真正的 ToolMessage 埋在 update["messages"] 里、
    Command 本身没有 tool_call_id。取首个带 tool_call_id 的 message 当结果；
    取不到返 None（让调用方 early return，不发 tool_result）。
    """
    if isinstance(output, Command):
        update = output.update if isinstance(output.update, dict) else {}
        for m in update.get("messages") or []:
            if getattr(m, "tool_call_id", None):
                return m
        return None
    return output


# ============ 单例块通用 helper（text / thinking 共用） ============

async def _emit_singleton_delta(
        state: StreamState,
        slot: SingletonSlot,
        type_name: str,
        delta_type: str,
        delta_key: str,
        content: str,
) -> AsyncIterator[AdapterEvent]:
    """单例块"如果没开就开 + 发 delta"模式 —— text / thinking 共用，消除重复。"""
    if not content:
        return

    if slot.index is None:
        slot.index = state.allocate()
        yield EventType.CONTENT_BLOCK_START, {
            "index": slot.index,
            "type": type_name,
        }
    yield EventType.CONTENT_BLOCK_DELTA, {
        "index": slot.index,
        "type": delta_type,
        delta_key: content,
    }


async def _emit_singleton_stop(slot: SingletonSlot) -> AsyncIterator[AdapterEvent]:
    """关闭单例块。开着就发 STOP + 清空 slot；没开就 noop。"""
    if slot.index is not None:
        yield EventType.CONTENT_BLOCK_STOP, {"index": slot.index}
        slot.index = None


# ============ tool 流处理（结构特殊，单独写） ============

async def _emit_tool_call_chunk(
        state: StreamState, tc: Any,
) -> AsyncIterator[AdapterEvent]:
    """处理单个 ToolCallChunk：首条带 name + id 时开块、后续 args 流式 delta。"""
    chunk_index = _tc_field(tc, "index")
    if chunk_index is None:
        return
    tc_name = _tc_field(tc, "name")
    tc_id = _tc_field(tc, "id")
    tc_args = _tc_field(tc, "args")

    # 首条：开块（必须同时拿到 name + id）
    if chunk_index not in state.tools.chunk_to_block:
        if not tc_name or not tc_id:
            return  # 等首条带齐 name + id
        block_idx = state.allocate()
        state.tools.register(chunk_index, block_idx, tc_id)
        yield EventType.TOOL_USE_START, {
            "index": block_idx,
            "id": tc_id,
            "name": tc_name,
            "input_preview": TOOL_INPUT_PREVIEW_DEFAULT,
        }

    # args 流式 delta（partial JSON 串增量；前端自己累积解析）
    if tc_args:
        block_idx = state.tools.chunk_to_block[chunk_index]
        tool_id = state.tools.block_to_id.get(block_idx, "")
        yield EventType.TOOL_USE_DELTA, {
            "index": block_idx,
            "id": tool_id,
            "type": DELTA_TYPE_INPUT_JSON,
            "partial_json": tc_args,
        }


# ============ 关块共用逻辑（不变式：唯一关块入口） ============

async def _close_open_blocks(state: StreamState) -> AsyncIterator[AdapterEvent]:
    """关掉所有还活着的块、发 *_STOP 事件。

    **唯一关块入口** —— 正常路径（_on_chat_model_end）和异常兜底共用，避免漂移。
    """

    async for ev in _emit_singleton_stop(state.text):
        yield ev
    async for ev in _emit_singleton_stop(state.thinking):
        yield ev

    for chunk_index in list(state.tools.chunk_to_block.keys()):
        released = state.tools.release(chunk_index)
        if released is None:
            continue
        block_idx, tool_id = released
        yield EventType.TOOL_USE_STOP, {
            "index": block_idx,
            "id": tool_id,
        }


# ============ Handler ============

@_register("on_chat_model_stream")
async def _on_chat_model_stream(
        state: StreamState, data: dict[str, Any],
) -> AsyncIterator[AdapterEvent]:
    """一个 AIMessageChunk 可能同时带 text / reasoning / tool_call_chunks，各自分流。"""
    chunk = data.get("chunk")
    if chunk is None:
        return

    async for ev in _emit_singleton_delta(
            state, state.text, BLOCK_TEXT, DELTA_TYPE_TEXT, DELTA_KEY_TEXT, _extract_text(chunk),
    ):
        yield ev
    async for ev in _emit_singleton_delta(
            state, state.thinking, BLOCK_THINKING, DELTA_TYPE_THINKING, DELTA_KEY_THINKING, _extract_reasoning(chunk),
    ):
        yield ev
    for tc in getattr(chunk, "tool_call_chunks", None) or []:
        async for ev in _emit_tool_call_chunk(state, tc):
            yield ev


@_register("on_chat_model_end")
async def _on_chat_model_end(
        state: StreamState, data: dict[str, Any],
) -> AsyncIterator[AdapterEvent]:
    """模型一轮 chat 完事：关所有活块 + 发 message_delta(usage)。"""
    async for ev in _close_open_blocks(state):
        yield ev

    output = data.get("output")
    usage = getattr(output, "usage_metadata", None) if output else None
    input_tokens = usage.get("input_tokens", 0) if usage else 0
    output_tokens = usage.get("output_tokens", 0) if usage else 0

    yield EventType.MESSAGE_DELTA, {
        "stop_reason": DEFAULT_STOP_REASON,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


@_register("on_tool_end")
async def _on_tool_end(
        state: StreamState, data: dict[str, Any],
) -> AsyncIterator[AdapterEvent]:
    """工具执行完成：从 ToolMessage.tool_call_id 反查 block、发 tool_result。"""
    output = data.get("output")
    output = _unwrap_tool_output(output) # ← 新增：Command → 内部 ToolMessage
    if output is None:
        return
    tool_call_id = getattr(output, "tool_call_id", None)
    if not tool_call_id:
        return
    block_idx = state.tools.id_to_block.get(tool_call_id)
    if block_idx is None:
        return

    content = getattr(output, "content", None)
    yield EventType.TOOL_RESULT, {
        "index": block_idx,
        "id": tool_call_id,
        "status": "success",
        "result_summary": _summarize_tool_result(content),
        "result_data": content,
    }


# ============ 主入口 ============

async def adapt_chat_stream(
        events: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[AdapterEvent]:
    """LangChain astream_events(v2) → 我们的结构化事件流。

        Args:
            events: `graph.astream_events(input, version="v2")` 的产物
        Yields:
            (EventType, payload) 元组 —— SSE 序列化 / sink 分发由 runner 统一做
    """

    state = StreamState()

    try:
        async for ev in events:
            handler = _HANDLERS.get(ev.get("event", ""))
            if handler is None:
                continue
            agent_name = (ev.get("metadata") or {}).get("lc_agent_name")
            async for evt_type, payload in handler(state, ev.get("data", {})):
                if agent_name is not None:
                    payload = {**payload, "subagent": agent_name}
                yield evt_type, payload
    except Exception:
        # 内部异常完整 log 给后端；对前端只发通用文案，防细节外泄（栈 / 路径 / SQL）
        logger.exception("adapt_chat_stream failed; emitting cleanup + error event")
        # 兜底自包 try：清理 / 发错误事件各自再炸也不让 generator 二次失败
        try:
            async for out in _close_open_blocks(state):
                yield out
        except Exception:
            logger.exception("failed to close open blocks during error cleanup")
        try:
            yield EventType.ERROR, {
                "code": ERROR_CODE_INTERNAL,
                "message": ERROR_MESSAGE_GENERIC,
            }
        except Exception:
            logger.exception("failed to emit error event")
