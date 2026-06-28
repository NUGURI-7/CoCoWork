from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.mcp import (
    MCPServerCreate,
    MCPServerOut,
    MCPServerUpdate,
    MCPTestConnectionIn,
    MCPTestConnectionOut,
    MCPToolBrief,
)
from app.services.mcp import MCPServerService, get_mcp_server_service

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]
MCPServerServiceDep = Annotated[MCPServerService, Depends(get_mcp_server_service)]


@router.post("", summary="创建 MCP server")
async def create_mcp_server(
    data: MCPServerCreate,
    current_user: CurrentUserDep,
    svc: MCPServerServiceDep,
) -> ResponseModel[MCPServerOut]:
    server = await svc.create(current_user, data)
    return success(data=MCPServerOut.model_validate(server), message="创建成功")


@router.post("/test", summary="测试 MCP server 连接")
async def test_mcp_connection(
    data: MCPTestConnectionIn,
    current_user: CurrentUserDep,
    svc: MCPServerServiceDep,
) -> ResponseModel[MCPTestConnectionOut]:
    ok, tools, error = await svc.test_connection(
        data.server_url, data.transport, data.headers
    )
    return success(
        data=MCPTestConnectionOut(
            success=ok,
            tool_count=len(tools),
            tools=[
                MCPToolBrief(name=t.name, description=t.description or "")
                for t in tools
            ],
            error=error,
        )
    )


@router.get("", summary="列出自己的 MCP server")
async def list_mcp_servers(
    current_user: CurrentUserDep,
    svc: MCPServerServiceDep,
) -> ResponseModel[list[MCPServerOut]]:
    servers = await svc.list_own(current_user)
    return success(data=[MCPServerOut.model_validate(s) for s in servers])


@router.get("/{server_id}", summary="MCP server 详情")
async def get_mcp_server(
    server_id: UUID,
    current_user: CurrentUserDep,
    svc: MCPServerServiceDep,
) -> ResponseModel[MCPServerOut]:
    server = await svc.get_by_id(current_user, server_id)
    return success(data=MCPServerOut.model_validate(server))


@router.put("/{server_id}", summary="更新 MCP server")
async def update_mcp_server(
    server_id: UUID,
    data: MCPServerUpdate,
    current_user: CurrentUserDep,
    svc: MCPServerServiceDep,
) -> ResponseModel[MCPServerOut]:
    server = await svc.update(current_user, server_id, data)
    return success(data=MCPServerOut.model_validate(server), message="更新成功")


@router.delete("/{server_id}", summary="删除 MCP server")
async def delete_mcp_server(
    server_id: UUID,
    current_user: CurrentUserDep,
    svc: MCPServerServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, server_id)
    return success(message="删除成功")
