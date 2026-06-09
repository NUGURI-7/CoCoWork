"""Conversation 请求/响应 schema。

URL nested 在 /workspaces/{workspace_id}/conversations/* 下,
workspace_id 走 URL path,不进 body schema。

title 可空字符串(创建时不强求传,等首条用户消息后系统再自动生成)。
config 宽松 dict,对话级临时覆盖(换模型 / 开 thinking / 临时挂 KB)。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    """创建 conversation 请求体。

    title 可不传,新建对话默认空字符串,等首条用户消息后由系统生成标题。
    """

    title: str = Field(default="", max_length=150, description="对话标题(可后置自动生成)")


class ConversationUpdate(BaseModel):
    """更新 conversation 请求体(PATCH 风格)。"""

    title: str | None = Field(default=None, max_length=150)
    config: dict[str, Any] | None = None


class ConversationOut(BaseModel):
    """conversation 对外输出。"""

    id: UUID
    workspace_id: UUID
    title: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)