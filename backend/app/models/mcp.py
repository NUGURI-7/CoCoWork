"""外部 MCP server 配置（消费侧 / MCP Client）。

CoCoWork 作为 MCP Client，消费用户配置的外部 MCP server 暴露的工具。
本质同 Provider：用户配一次、带加密凭据、可被多个 agent 复用的外部连接源。
只存「怎么连上这个 server」；工具清单运行时 tools/list 实时发现，
tools_cache 仅为列表展示 / 离线浏览的缓存，不是真相来源。
"""

from enum import StrEnum

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class MCPTransport(StrEnum):
    """MCP 远端传输协议。"""

    STREAMABLE_HTTP = "streamable_http"  # 新标准，推荐
    SSE = "sse"  # 旧协议，降级兼容


class MCPServer(UUIDBaseModel, TimestampMixin):
    """用户配置的外部 MCP server（Client 侧）。"""

    created_by = fields.ForeignKeyField(
        "models.User", related_name="mcp_servers", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=100, description="显示名")
    server_url = fields.CharField(max_length=1024, description="MCP server 端点 URL")
    transport = fields.CharEnumField(
        MCPTransport,
        max_length=32,
        default=MCPTransport.STREAMABLE_HTTP,
        description="传输协议：streamable_http（推荐）/ sse（降级）",
    )
    headers_encrypted = fields.TextField(
        null=True,
        description="自定义请求头 dict（含鉴权 token，Fernet 加密；无则 NULL）",
    )
    description = fields.CharField(max_length=500, default="", description="备注")
    enabled = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "mcp_servers"