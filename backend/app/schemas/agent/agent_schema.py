from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field



class AgentCreate(BaseModel):
    """创建 Agent 请求体。"""
    name: str = Field(min_length=1, max_length=150, description="Agent 名字")
    description: str = Field(default="", max_length=500, description="描述")
    template: str = Field(min_length=1, max_length=64, description="引用的内置模板 key")
    config: dict[str, Any] = Field(default_factory=dict, description="填料：行为 + 挂载资源")


class AgentUpdate(BaseModel):
    """更新 Agent 请求体。template 创建后锁死（要换形态 = 重建）。"""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] | None = None

class AgentOut(BaseModel):
    """Agent 对外输出。"""

    id: UUID
    name: str
    description: str
    template: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
