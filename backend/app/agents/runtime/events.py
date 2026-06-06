"""Runtime 层事件协议：SSE 事件类型 + 序列化工具。

定义对话流式输出的 SSE 事件名（对齐 Anthropic Claude API 风格 + 自定义 tool_use 扩展），
配合 `sse_event(event, data)` 把事件 + 字典 payload 序列化成 SSE 帧文本。

事件 payload 故意不建 pydantic schema —— 流式场景 dict yield 更轻量、字段也松散；
事件协议本身由文档（参考旧项目 `streaming-render.md`）锁定，不依赖运行时校验。

被 `runtime/adapter.py` 翻译 LangChain 事件时调用，被 route 层 StreamingResponse 直接消费。
"""

import json
from enum import StrEnum
from typing import Any



class EventType(StrEnum):
    """SSE 事件名（对齐 Anthropic messages.stream 命名 + 自定义 tool 扩展）。"""

    # P0 — 文本流
    MESSAGE_START = "message_start"
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_BLOCK_DELTA = "content_block_delta"
    CONTENT_BLOCK_STOP = "content_block_stop"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"
    ERROR = "error"

    # P1 — 工具调用（占位、P0 适配器不实现）
    TOOL_USE_START = "tool_use_start"
    TOOL_USE_DELTA = "tool_use_delta"
    TOOL_USE_STOP = "tool_use_stop"
    TOOL_RESULT = "tool_result"


def sse_event(event: EventType | str, data: dict[str, Any]) -> str:
    """把事件类型 + 字典 payload 序列化成 SSE 帧（`event: ...\\ndata: ...\\n\\n`）。

        `ensure_ascii=False` —— 中文不被 escape 成 `\\uXXXX`，前端拿到的就是原文。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


































