"""Chat 流式入参 schema —— Playground / 未来 Workspace 调用 agent 跑对话时共用。

content 与 history.content 都走 block 数组形态：
- TextBlock         —— 文本
- ArtifactRefBlock  —— 用户拖进来的历史产物引用（P5 决策 25）
- 未来：ToolUseBlock（多轮 tool call 上下文回放）、ImageBlock（vision 多模态输入）

形态从 P0 锁定为数组，扩 union 不动上层。

不绑 playground / workspace 任何场景，是通用对话能力的 HTTP 契约。
"""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """文本块。"""
    type: Literal["text"] = "text"
    text: str


class ArtifactRefBlock(BaseModel):
    """用户从产出物面板拖进来的产物引用（决策 25）。

    **请求里只有 artifact_id 作数**：filename / size 是服务端查库回填后
    才落进 DB 的展示字段（前端渲染附件 chip、回放历史给模型看清单都靠它）。
    客户端传了也一律被覆盖 —— 它手上那份可能是旧的，更不该成为「取哪个文件」
    的依据。取字节与归属校验永远只认 artifact_id。
    """
    type: Literal["artifact_ref"] = "artifact_ref"
    artifact_id: UUID
    filename: str = ""
    size: int = 0
    content_type: str = ""


# 判别式 union：按 type 字段分派，扩新块类型时加一个成员即可，
# 上层（ChatStreamRequest / ConversationStreamIn / MessageOut）一行不动
ContentBlock = Annotated[TextBlock | ArtifactRefBlock, Field(discriminator="type")]



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