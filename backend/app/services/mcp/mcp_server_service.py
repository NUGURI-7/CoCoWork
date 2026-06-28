import json
import logging
from uuid import UUID

from langchain_core.tools import BaseTool

from app.core.encryption import decrypt, encrypt
from app.core.exceptions.types import NotFound404
from app.models.mcp import MCPServer
from app.models.user import User
from app.schemas.mcp import MCPServerCreate, MCPServerUpdate
from app.services.mcp.mcp_runtime import fetch_mcp_tools

logger = logging.getLogger(__name__)


class MCPServerService:
    """MCP server CRUD。

    可见性：用户只能看到自己创建的 MCP server。
    headers 含鉴权 token，整体 JSON 序列化后 Fernet 加密存储。
    """

    async def get_by_id(self, user: User, server_id: UUID) -> MCPServer:
        """获取用户自己的 MCP server，不存在或非本人则 404。"""
        server = await MCPServer.filter(id=server_id, created_by=user).first()
        if server is None:
            raise NotFound404("MCP server 不存在")
        return server

    async def create(self, user: User, data: MCPServerCreate) -> MCPServer:
        return await MCPServer.create(
            created_by=user,
            name=data.name,
            server_url=data.server_url,
            transport=data.transport,
            headers_encrypted=self._encrypt_headers(data.headers),
            description=data.description,
            enabled=data.enabled,
        )

    async def update(
        self, user: User, server_id: UUID, data: MCPServerUpdate
    ) -> MCPServer:
        await self.get_by_id(user, server_id)  # 归属校验

        update_fields: dict = {}
        if data.name is not None:
            update_fields["name"] = data.name
        if data.server_url is not None:
            update_fields["server_url"] = data.server_url
        if data.transport is not None:
            update_fields["transport"] = data.transport
        if data.headers is not None:
            update_fields["headers_encrypted"] = self._encrypt_headers(data.headers)
        if data.description is not None:
            update_fields["description"] = data.description
        if data.enabled is not None:
            update_fields["enabled"] = data.enabled

        if update_fields:
            await MCPServer.filter(id=server_id).update(**update_fields)

        return await MCPServer.get(id=server_id)

    async def list_own(self, user: User) -> list[MCPServer]:
        """返回用户自己创建的 MCP server。"""
        return await MCPServer.filter(created_by=user).order_by("-created_at")

    async def delete(self, user: User, server_id: UUID) -> None:
        server = await self.get_by_id(user, server_id)
        await server.delete()

    async def get_decrypted_headers(self, server: MCPServer) -> dict[str, str]:
        """解密自定义请求头（仅内部调用，不暴露给路由层）。"""
        if not server.headers_encrypted:
            return {}
        return json.loads(decrypt(server.headers_encrypted))

    async def test_connection(
        self, server_url: str, transport: str, headers: dict[str, str]
    ) -> tuple[bool, list[BaseTool], str | None]:
        """试连一个 MCP server，返回 (是否成功, 工具列表, 错误信息)。

        捕获所有异常转成 (False, [], 错误文案)——测试连接的「失败」是正常
        业务结果（用户配错了），不该 500，由端点组装成结构化响应给前端。
        """
        try:
            tools = await fetch_mcp_tools(server_url, transport, headers)
            return True, tools, None
        except Exception as e:
            logger.warning("MCP 测试连接失败 url=%s: %s", server_url, e)
            return False, [], str(e)

    @staticmethod
    def _encrypt_headers(headers: dict[str, str]) -> str | None:
        """headers dict → 加密字符串；空则 None。"""
        if not headers:
            return None
        return encrypt(json.dumps(headers))


async def get_mcp_server_service() -> MCPServerService:
    return MCPServerService()
