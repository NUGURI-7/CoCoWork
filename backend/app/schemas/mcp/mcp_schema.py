from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MCPTransportType = Literal["streamable_http", "sse"]


class MCPServerCreate(BaseModel):
    """创建 MCP server 请求体。"""

    name: str = Field(min_length=1, max_length=100, description="显示名")
    server_url: str = Field(min_length=1, max_length=1024, description="MCP server 端点 URL")
    transport: MCPTransportType = Field(default="streamable_http", description="传输协议")
    headers: dict[str, str] = Field(
        default_factory=dict, description="自定义请求头（明文，后端加密存储；无则留空）",
    )
    description: str = Field(default="", max_length=500, description="备注")
    enabled: bool = Field(default=True, description="是否启用")


class MCPServerUpdate(BaseModel):
    """更新 MCP server 请求体，全部 Optional。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    server_url: str | None = Field(default=None, min_length=1, max_length=1024)
    transport: MCPTransportType | None = None
    headers: dict[str, str] | None = Field(default=None, description="新请求头，留空不改")
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None


class MCPServerOut(BaseModel):
    """MCP server 对外输出（不含 headers）。"""

    id: UUID
    name: str
    server_url: str
    transport: str
    description: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MCPTestConnectionIn(BaseModel):
    """测试连接请求体（用配置直接试连，不依赖已存记录）。"""

    server_url: str = Field(min_length=1, max_length=1024)
    transport: MCPTransportType = Field(default="streamable_http")
    headers: dict[str, str] = Field(default_factory=dict)


class MCPToolBrief(BaseModel):
    """测试连接发现的工具摘要。"""

    name: str
    description: str


class MCPTestConnectionOut(BaseModel):
    """测试连接结果。success=False 时 error 给失败原因。"""

    success: bool
    tool_count: int
    tools: list[MCPToolBrief]
    error: str | None = None
