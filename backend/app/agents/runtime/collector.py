"""流式事件收集器 —— sink 的标准消费者。

runner 边流边把 (EventType, payload) 喂进来（`run_chat_stream(sink=collector.feed)`），
流完后调用方从桶里拿完整消息：message_id + blocks + 有没有出过错。

只攒不判：done / stopped 由调用方控制流位置判定（自然走完 = done、
中途被掐 = stopped），桶只记录"收到过 error 事件"这个事实。

不 import 任何业务模块（workspace / agent CRUD）—— 落库 / audit / replay
等任何要"留一份完整消息"的场景都能复用。
"""

from typing import Any

from app.agents.runtime.events import EventType


class MessageCollector:
    """攒一条流式 assistant 消息。

    blocks 落库形态 = SSE 事件攒平（snake_case、字段名与 SSE payload 一致），
    不带前端 UI 状态（collapsed / active）—— DB 存事实，UI 状态是前端的事。
    """

    def __init__(self) -> None:
        self.message_id: str = ""
        self.saw_error: bool = False
        self.error_message: str = ""
        # index → 块。delta / tool_result 事件都带 index 反查目标块，
        # dict 寻址 O(1)；出桶时按 index 升序还原成 list。
        self._blocks: dict[int, dict[str, Any]] = {}

    @property
    def blocks(self) -> list[dict[str, Any]]:
        """按 index 升序的完整块列表 —— 落库 content 的最终形态。"""
        return [self._blocks[i] for i in sorted(self._blocks)]

    def feed(self, event: EventType, payload: dict[str, Any]) -> None:
        """sink 入口 —— runner 每产一个事件喂一次。

        跑在 SSE hot path 上，必须轻、必须不抛（runner 的 _feed_sink
        有兜底，但那是保险不是许可）。未知事件静默跳过 —— 协议将来
        加新事件类型，旧桶不炸。
        """
        match event:
            case EventType.MESSAGE_START:
                self.message_id = payload.get("id", "")
            case EventType.CONTENT_BLOCK_START:
                self._open_block(payload)
            case EventType.CONTENT_BLOCK_DELTA:
                self._append_delta(payload)
            case EventType.TOOL_USE_START:
                self._open_tool_block(payload)
            case EventType.TOOL_USE_DELTA:
                self._append_tool_json(payload)
            case EventType.TOOL_RESULT:
                self._fill_tool_result(payload)
            case EventType.ERROR:
                self.saw_error = True
                self.error_message = payload.get("message", "")
            case _:
                # CONTENT_BLOCK_STOP / TOOL_USE_STOP / MESSAGE_DELTA /
                # MESSAGE_STOP —— 桶无动作：块的"完整性"由内容本身体现，
                # 不需要关块标记；usage 不落 Message 表，不攒。
                pass

    def _open_block(self, payload: dict[str, Any]) -> None:
        """content_block_start → 开 text / thinking 块，内容先置空串。"""
        index = payload.get("index")
        block_type = payload.get("type", "")
        if index is None or not block_type:
            return
        block: dict[str, Any] = {"type": block_type, block_type: ""}
        subagent = payload.get("subagent")
        if subagent:
            block["subagent"] = subagent
        delegate_id = payload.get("delegate_id")
        if delegate_id:
            block["delegate_id"] = delegate_id
        self._blocks[index] = block

    def _append_delta(self, payload: dict[str, Any]) -> None:
        """content_block_delta → 按 index 找块、追加内容增量。"""
        index = payload.get("index")
        block = self._blocks.get(index)
        if block is None:
            return
        key = block["type"]
        delta = payload.get(key)
        if isinstance(delta, str):
            block[key] += delta

    def _open_tool_block(self, payload: dict[str, Any]) -> None:
        """tool_use_start → 开 tool 块；结果字段占位，等 tool_result 回填。"""
        index = payload.get("index")
        if index is None:
            return

        block: dict[str, Any] = {
            "type": "tool_use",
            "id": payload.get("id", ""),
            "name": payload.get("name", ""),
            "input_preview": payload.get("input_preview", ""),
            "partial_json": "",
            "result_summary": None,
            "result_data": None,
            "status": None,
        }
        subagent = payload.get("subagent")
        if subagent:
            block["subagent"] = subagent
        delegate_id = payload.get("delegate_id")
        if delegate_id:
            block["delegate_id"] = delegate_id
        self._blocks[index] = block

    def _append_tool_json(self, payload: dict[str, Any]) -> None:
        """tool_use_delta → 追加 partial JSON 增量（攒齐即完整入参串）。"""
        index = payload.get("index")
        block = self._blocks.get(index)
        if block is None:
            return
        delta = payload.get("partial_json")
        if isinstance(delta, str):
            block["partial_json"] += delta

    def _fill_tool_result(self, payload: dict[str, Any]) -> None:
        """tool_result → 回填结果三件套 + 结局 status。"""
        index = payload.get("index")
        block = self._blocks.get(index)
        if block is None:
            return
        block["status"] = payload.get("status")
        block["result_summary"] = payload.get("result_summary")
        block["result_data"] = payload.get("result_data")
