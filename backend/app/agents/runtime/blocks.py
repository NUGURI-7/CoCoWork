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
from uuid import UUID

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

    @property
    def result_text(self) -> str:
        """工具结果的文本形态 —— 回放进历史时用。

        result_data 的类型随工具而定:自家工具统一返 str,MCP 那条路来的
        可能是 list / dict(LangChain ToolMessage.content 本就允许)。类型
        判断收口在解析层,下游(回放渲染、将来的压缩)只吃字符串。

        没结局的块(用户中途点了停止)result_data 是 None → 空串,由调用方
        决定怎么表达「没有结果」。
        """
        data = self.result_data
        if data is None:
            return ""
        if isinstance(data, str):
            return data.strip()
        return json.dumps(data, ensure_ascii=False)


class ArtifactRefBlock(_BlockBase):
    """用户拖进输入框的产物引用（决策 25）—— 落库那一份。

    与 schemas/agent/chat_schema.py 里的同名类**是两层不同的东西**（同 TextBlock）：
    那份是 HTTP 请求契约，收进来时只有 artifact_id 可信；这份是从 jsonb 读回来的
    历史，filename / size 当时已由服务端回填好，直接可用。

    **artifact_id 没有默认值**，与本模块「缺字段吃默认值」的通例相反：身份字段
    没有合理的默认值可吃，缺了它这个块就什么都不是。让它整块被 parse_blocks
    跳掉（并留一条 warning），好过留个空壳往下游漂。
    """

    type: Literal["artifact_ref"]
    artifact_id: UUID
    filename: str = ""
    size: int = 0


class AskBlock(_BlockBase):
    """人工确认的表单 —— 停下来问用户的那一张。

    存进 content 而不是只发一帧 SSE：否则用户刷新页面后，这条消息只剩一个
    「卡着」的状态，前端不知道该渲染什么表单，等于死在那儿。

    answer 为 None = 还没答。答完由「继续」接口回填，历史里就能看到
    「当时问了什么、我答了什么」，而不只是一行工具调用记录。
    """

    type: Literal["ask"]
    interrupt_id: str = ""  # LangGraph 给这次中断分配的 id
    payload: dict[str, Any] = {}  # AskPayload 的原样内容（问题 / 字段 / 按钮）
    answer: dict[str, Any] | None = None


ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ArtifactRefBlock | AskBlock

_BLOCK_TYPES: dict[str, type[ContentBlock]] = {
    "text": TextBlock,
    "thinking": ThinkingBlock,
    "tool_use": ToolUseBlock,
    "artifact_ref": ArtifactRefBlock,
    "ask": AskBlock,
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





