"""Message.content 的块级类型 —— jsonb 与业务逻辑之间的解析层。

collector 落库的每个块是裸 dict(SSE 事件攒平);这里给它们定强类型模型,
边界处一次 parse_blocks() 解析干净,下游(assembler / 未来压缩管线)只吃
类型化对象,不再满地 .get() 摸黑。

Parse, don't validate:脏数据(字段缺失 / partial_json 断半截 / 未知块类型)
全在解析层消化——缺字段吃默认值、未知类型整块跳过,下游永远拿到合法对象。
"""
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

class _BlockBase(BaseModel):
    """所有块共有的归属戳(无戳 = 消息发送者本人产出)。"""

    subagent: str | None = None
    delegate_id: str | None = None

class TextBlock(_BlockBase):
    type: Literal["text"]
    text: str = ""


class ThinkingBlock(_BlockBase):
    type: Literal["thinking"]
    thinking: str = ""

class ToolUseBlock(_BlockBase):
    type: Literal["tool_use"]
    id: str = ""
    name: str = ""
    input_preview: str = ""
    partial_json: str = ""
    result_summary: Any = None
    result_data: Any = None
    status: str | None = None

    @property
    def input_args(self) -> dict[str, Any]:
        """安全解析工具入参(partial_json 可能断在半截——流被掐)。"""
        try:
            args = json.loads(self.partial_json or "{}")
        except ValueError:
            return {}
        return args if isinstance(args, dict) else {}

ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock

_BLOCK_TYPES: dict[str, type[ContentBlock]] = {
    "text": TextBlock,
    "thinking": ThinkingBlock,
    "tool_use": ToolUseBlock,
}


def parse_blocks(raw: list[dict[str, Any]] | None) -> list[ContentBlock]:
    """jsonb 裸块列表 → 类型化块列表;未知类型 / 烂块跳过不炸。"""
    blocks: list[ContentBlock] = []
    for item in raw or []:
        cls = _BLOCK_TYPES.get(item.get("type", ""))
        if cls is None:
            continue
        try:
            blocks.append(cls.model_validate(item))
        except ValidationError:
            logger.warning("忽略无法解析的 content 块 type=%r", item.get("type"))
    return blocks





