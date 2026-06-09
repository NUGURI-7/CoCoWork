"""Workspace 请求/响应 schema。

WorkspaceCreate / Update / Out:API 层契约。
config / supervisor 在本层用宽松 dict[str, Any],强类型 schema(WorkspaceConfig / SupervisorConfig)
留到下一刀做,对齐 Agent 的 config_schema.py 范式(API 层宽松, 装配层强类型校验)。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class WorkspaceCreate(BaseModel):
    """创建 workspace 请求体。

    supervisor / config 创建时由后端给默认值,不需要用户传。
    """

    name: str = Field(min_length=1, max_length=150, description="工作空间名字")
    description: str = Field(default="", max_length=500, description="简介")
    avatar_url: str = Field(default="", max_length=500, description="头像 URL")


class WorkspaceUpdate(BaseModel):
    """更新 workspace 请求体(PATCH 风格,字段全可空)。"""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)
    supervisor: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class WorkspaceOut(BaseModel):
    """workspace 对外输出。"""

    id: UUID
    name: str
    description: str
    avatar_url: str
    supervisor: dict[str, Any]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)