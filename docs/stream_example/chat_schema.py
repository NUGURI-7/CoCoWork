"""
    @project: DaisyWind
    @Author: niu
    @file: chat_schema.py
    @date: 2026/2/12 17:10
    @desc:
"""
from datetime import datetime
from typing import Optional, Literal, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ==================== Content Block 定义 ====================
class TextBlock(BaseModel):
    """纯文本 block。user / assistant 都会用。"""
    type: Literal["text"] = "text"
    text: str

class ToolUseBlock(BaseModel):
    """assistant 发起的一次工具调用 + 结果。
        同一个 block 同时保存 input 和 output，回放时一次性还原。
    """
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str,Any]
    status: Literal["success", "error"] = "success"
    output: Any = None

class ImageBlock(BaseModel):
    """assistant 生成的图片 block（Nano Banana / Gemini 图像模型）。

        生命周期三态：
        - loading: 后端收到 FilePart，正在上传 R2
        - ready:   已上传成功，url 可访问
        - error:   上传失败，message 携带原因
    """
    type: Literal["image"] = "image"
    id: str
    status: Literal["loading","ready", "error"] = "loading"
    url: Optional[str] = None
    message: Optional[str] = None

ContentBlock = TextBlock | ToolUseBlock | ImageBlock

class ChatRequest(BaseModel):
    """发送消息请求"""
    conversation_uuid: str
    message_uuid: str # 前端生成 uuid
    content: list[ContentBlock]
    provider: str = "deepseek"
    model: str = "deepseek-chat"

class ConversationOut(BaseModel):
    """对话列表项"""
    uuid: UUID
    title: str
    model: str
    provider: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageOut(BaseModel):
    """消息"""
    uuid: UUID
    role: str
    content: list[ContentBlock]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationDetail(BaseModel):
    """对话详情（含消息列表"""
    uuid: UUID
    title: str
    model: str
    provider: str
    messages: list[MessageOut]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
