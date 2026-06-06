"""Chat 流式入参 schema —— Playground / 未来 Workspace 调用 agent 跑对话时共用。

content 与 history.content 都走 block 数组形态：
- P0 仅 TextBlock
- P1 扩 ToolUseBlock（多轮 tool call 上下文回放需要）
- P2 扩 ImageBlock（vision 多模态视觉输入）

形态从 P0 锁定为数组，未来扩 union 不动上层。

不绑 playground / workspace 任何场景，是通用对话能力的 HTTP 契约。
"""
from typing import Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """文本块（P0 唯一 block 类型）。"""
    type: Literal["text"] = "text"
    text: str


# P0：union 只有 TextBlock；P1 扩 ToolUseBlock、P2 扩 ImageBlock 时在这里加
ContentBlock = TextBlock



class HistoryMessage(BaseModel):
    """一条历史消息。沙盒不入库，由前端持有并整段送回。"""

    role: Literal["user", "assistant"]
    content: list[ContentBlock]

class ChatStreamRequest(BaseModel):
    """流式对话请求 = 当前轮 user 输入（block 数组） + 前几轮 history。

    模型 / system_prompt / 资源挂载全部从 path 上的 agent 拉，请求体不覆盖
    （Playground 按 Agent 当前保存的配置跑、不是临时换模型场景）。
    """

    content: list[ContentBlock] = Field(
        ..., min_length=1, description="当前轮 user 输入 block 数组"
    )
    history: list[HistoryMessage] = Field(default_factory=list, description="之前几轮对话")