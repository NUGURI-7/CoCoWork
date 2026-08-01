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
class LaneState:
    """一条"泳道"的活块状态 —— 一次 task 派发(及其子 agent 全程)独占一条。

    只是把原有的 text / thinking 单例槽 + ToolRegistry 打包进来，按道各持一份：
    并发两路子 agent 各走各的道，各自的 chunk.index 0 互不相撞
    （修掉工具入参串块、正文串段的 bug）。三个成员的类型全是原样复用。
    """

    key: str  # 本道的泳道键（LANE_MAIN 或 "tools:<uuid>"）——handler 靠它认出自己是不是主道
    text: SingletonSlot = field(default_factory=SingletonSlot)
    thinking: SingletonSlot = field(default_factory=SingletonSlot)
    tools: ToolRegistry = field(default_factory=ToolRegistry)


@dataclass
class StreamState:
    """全流状态：全局块编号 + 各泳道的活块。

    next_index 仍全局单调 —— 块编号跨道唯一，前端拿 index 当 key 不会撞。
    原来的 text / thinking / tools 三个平铺字段，下沉进各条 LaneState；本级只留
    全局计数 + 泳道表（按 _lane_key() 懒建）。
    """

    next_index: int = 0
    lanes: dict[str, "LaneState"] = field(default_factory=dict)
    # 第 2 步：把子 agent 的块归到正确的派活卡片
    task_call_by_pos: dict[int, str] = field(default_factory=dict)  # supervisor 第几个 task 调用 → call_id
    lane_to_delegate: dict[str, str] = field(default_factory=dict)  # 泳道键 → 它归属的 task call_id
    # 工具 name → 中文展示名（装配期算好、开流时传进来）。查不到的工具不盖这个
    # 字段，前端回落显示原始 name
    display_names: dict[str, str] = field(default_factory=dict)


    def allocate(self) -> int:
        """领一个新的块编号。"""
        idx = self.next_index
        self.next_index += 1
        return idx

    def lane(self, key: str) -> "LaneState":
        """取（懒建）某条泳道的状态。"""
        return self.lanes.setdefault(key, LaneState(key=key))

LANE_MAIN = "main"

def _lane_key(metadata: dict[str, Any]) -> str:
    """事件归属的"泳道"键。

    langgraph 给每次 task 派发一个独立的 checkpoint_ns 段 `tools:<uuid>`，该次派发
    衍生的所有子孙事件（子 agent 的多轮 model、各次 tool）都继承它。取 ns 里**第一个**
    `tools:` 段作键：它在一整条子 agent 执行期间保持稳定（更深的 `model:` / 嵌套
    `tools:` 段每轮都换），于是把整条子 agent 归到同一条道。supervisor 自身事件
    的 ns 不含 `tools:` 段 → 主道 LANE_MAIN。
    """
    ns = metadata.get("langgraph_checkpoint_ns") or ""
    for seg in ns.split("|"):
        if seg.startswith("tools:"):
            return seg
    return LANE_MAIN


def _push_pos(metadata: dict[str, Any]) -> int | None:
    """取这次 task 是"第几个"被派发的。

    on_tool_start 的 metadata.langgraph_path 形如 ["__pregel_push", <pos>, false]，
    <pos> 正是该 task 在 supervisor 消息里的排位，跟 task_call_by_pos 的键对得上。
    """
    path = metadata.get("langgraph_path") or []
    if len(path) >= 2 and isinstance(path[1], int):
        return path[1]
    return None


# ============ Dispatch 表 ============

# adapter 对外吐的事件原料：(事件类型, payload dict)。粘成 SSE 字符串是 runner 的活。
AdapterEvent = tuple[EventType, dict[str, Any]]

Handler = Callable[[StreamState, "LaneState", dict[str, Any]], AsyncIterator[AdapterEvent]]
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
        state: StreamState, lane: LaneState, tc: Any,
) -> AsyncIterator[AdapterEvent]:
    """处理单个 ToolCallChunk：首条带 name + id 时开块、后续 args 流式 delta。

    chunk.index 按**泳道**索引（lane.tools）：并发子 agent 各自的 index 0 互不干扰；
    block 编号仍走全局 state.allocate()，跨道唯一。
    """
    chunk_index = _tc_field(tc, "index")
    if chunk_index is None:
        return
    tc_name = _tc_field(tc, "name")
    tc_id = _tc_field(tc, "id")
    tc_args = _tc_field(tc, "args")

    # 首条：开块（必须同时拿到 name + id）
    if chunk_index not in lane.tools.chunk_to_block:
        if not tc_name or not tc_id:
            return  # 等首条带齐 name + id
        block_idx = state.allocate()
        lane.tools.register(chunk_index, block_idx, tc_id)
        # 第 2 步：记下 supervisor 第几个 task 调用 → call_id（回头按"第几个"查回它）
        if tc_name == "task":
            state.task_call_by_pos[chunk_index] = tc_id
        payload: dict[str, Any] = {
            "index": block_idx,
            "id": tc_id,
            "name": tc_name,
            "input_preview": TOOL_INPUT_PREVIEW_DEFAULT,
        }
        # 查不到就不加这个 key（而非塞 None）—— 与 subagent / delegate_id 同一写法，
        # 落库时 jsonb 里也不会多出一堆 null
        if display_name := state.display_names.get(tc_name):
            payload["display_name"] = display_name
        yield EventType.TOOL_USE_START, payload

    # args 流式 delta（partial JSON 串增量；前端自己累积解析）
    if tc_args:
        block_idx = lane.tools.chunk_to_block[chunk_index]
        tool_id = lane.tools.block_to_id.get(block_idx, "")
        yield EventType.TOOL_USE_DELTA, {
            "index": block_idx,
            "id": tool_id,
            "type": DELTA_TYPE_INPUT_JSON,
            "partial_json": tc_args,
        }


# ============ 关块共用逻辑（不变式：唯一关块入口） ============

async def _close_lane(lane: LaneState) -> AsyncIterator[AdapterEvent]:
    """关掉**某一条道**上还活着的块、发 *_STOP。

    一轮 model 收尾（_on_chat_model_end，只关本道）与异常兜底（_close_all 遍历各道）
    共用，逻辑与原 _close_open_blocks 一致，只是作用域缩到单道。
    """
    async for ev in _emit_singleton_stop(lane.text):
        yield ev
    async for ev in _emit_singleton_stop(lane.thinking):
        yield ev

    for chunk_index in list(lane.tools.chunk_to_block.keys()):
        released = lane.tools.release(chunk_index)
        if released is None:
            continue
        block_idx, tool_id = released
        yield EventType.TOOL_USE_STOP, {
            "index": block_idx,
            "id": tool_id,
        }


async def _close_all(state: StreamState) -> AsyncIterator[AdapterEvent]:
    """关掉所有道的活块（异常兜底用）。"""
    for lane in state.lanes.values():
        async for ev in _close_lane(lane):
            yield ev


# ============ Handler ============

@_register("on_chat_model_stream")
async def _on_chat_model_stream(
        state: StreamState, lane: LaneState, data: dict[str, Any],
) -> AsyncIterator[AdapterEvent]:
    """一个 AIMessageChunk 可能同时带 text / reasoning / tool_call_chunks，各自分流到本道。"""
    chunk = data.get("chunk")
    if chunk is None:
        return

    async for ev in _emit_singleton_delta(
            state, lane.text, BLOCK_TEXT, DELTA_TYPE_TEXT, DELTA_KEY_TEXT, _extract_text(chunk),
    ):
        yield ev
    async for ev in _emit_singleton_delta(
            state, lane.thinking, BLOCK_THINKING, DELTA_TYPE_THINKING, DELTA_KEY_THINKING, _extract_reasoning(chunk),
    ):
        yield ev
    for tc in getattr(chunk, "tool_call_chunks", None) or []:
        async for ev in _emit_tool_call_chunk(state, lane, tc):
            yield ev


@_register("on_chat_model_end")
async def _on_chat_model_end(
        state: StreamState, lane: LaneState, data: dict[str, Any],
) -> AsyncIterator[AdapterEvent]:
    """模型一轮 chat 完事：关**本道**活块 + 发 message_delta(usage)。

    主道 / 子道都发 —— 成员的调用同样烧 token，本轮总消耗要算上它们。
    下游分主 / 子不靠新字段：本模块主循环会给子道事件盖 delegate_id 戳，
    主道事件没有这个字段，**有没有它就是判据**。层 B 的上下文判据只认没戳的
    那些（collector 里分流），与总消耗统计互不干扰。
    """
    async for ev in _close_lane(lane):
        yield ev

    # usage_metadata 是 LangChain 的标准字段；provider 不回报时为 None
    # （如未开 stream_usage 的 OpenAI 兼容端点）—— 拿不到就不发。
    usage = getattr(data.get("output"), "usage_metadata", None)
    if not usage:
        return
    yield EventType.MESSAGE_DELTA, {
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


@_register("on_tool_end")
async def _on_tool_end(
        state: StreamState, lane: LaneState, data: dict[str, Any],
) -> AsyncIterator[AdapterEvent]:
    """工具执行完成：从 ToolMessage.tool_call_id 反查 block、发 tool_result。

    id 反查遍历各道：task 派活块在主道注册、其结果事件却落在子道，所以本事件的 lane
    未必是注册时那条；tool_call_id 全局唯一，扫一遍各道的 id_to_block 即可命中。
    """
    output = data.get("output")
    output = _unwrap_tool_output(output)  # Command → 内部 ToolMessage
    if output is None:
        return
    tool_call_id = getattr(output, "tool_call_id", None)
    if not tool_call_id:
        return

    block_idx = None
    for ln in state.lanes.values():
        if tool_call_id in ln.tools.id_to_block:
            block_idx = ln.tools.id_to_block[tool_call_id]
            break
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
        display_names: dict[str, str] | None = None,
) -> AsyncIterator[AdapterEvent]:
    """LangChain astream_events(v2) → 我们的结构化事件流。

        Args:
            events: `graph.astream_events(input, version="v2")` 的产物
            display_names: 工具 name → 中文展示名，装配期算好；缺省则所有
                工具都不带展示名，前端回落显示原始 name（= 本参数加进来之前的行为）
        Yields:
            (EventType, payload) 元组 —— SSE 序列化 / sink 分发由 runner 统一做
    """

    state = StreamState(display_names=display_names or {})

    try:
        async for ev in events:
            meta = ev.get("metadata") or {}
            # 摘要中间件的内部 LLM 调用会冒进事件流（dump 实证：token 级泄漏、
            # 与主模型同 ns）—— 按官方 lc_source 戳整体拦下，不渲染不落库
            if meta.get("lc_source") == "summarization":
                continue
            # 第 2 步 · 登记：task 一开始 → 记「本泳道 → 这次 task 的 call_id」。
            # 必须抢在下面 handler 判断之前 —— on_tool_start 无注册 handler，会被 continue 跳过。
            if ev.get("event") == "on_tool_start" and ev.get("name") == "task":
                pos = _push_pos(meta)
                call_id = state.task_call_by_pos.get(pos) if pos is not None else None
                if call_id is not None:
                    state.lane_to_delegate[_lane_key(meta)] = call_id

            handler = _HANDLERS.get(ev.get("event", ""))
            if handler is None:
                continue
            agent_name = meta.get("lc_agent_name")
            lane_key = _lane_key(meta)
            lane = state.lane(lane_key)  # 按 ns 把事件归到对应泳道
            delegate_id = state.lane_to_delegate.get(lane_key)  # 第 2 步 · 盖戳：本道归属哪次派活
            async for evt_type, payload in handler(state, lane, ev.get("data", {})):
                if agent_name is not None:
                    payload = {**payload, "subagent": agent_name}
                # 不给"派活块自己"的事件盖戳（其 id == delegate_id，如 task 的 tool_result）——
                # 那类事件要落到主流的派活块本体上，而非被路由进它的子块里。
                if delegate_id is not None and payload.get("id") != delegate_id:
                    payload = {**payload, "delegate_id": delegate_id}
                yield evt_type, payload
    except Exception:
        # 内部异常完整 log 给后端；对前端只发通用文案，防细节外泄（栈 / 路径 / SQL）
        logger.exception("adapt_chat_stream failed; emitting cleanup + error event")
        # 兜底自包 try：清理 / 发错误事件各自再炸也不让 generator 二次失败
        try:
            async for out in _close_all(state):
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
