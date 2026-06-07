"""工具列表端点 —— 列出当前可装配的工具。

GET /tools  →  内置工具（从 registry 内存读，不查 DB）。

内置工具是代码注册的进程内单例、没有 DB 表，所以直接读 registry、不走 service。
未来 MCP / custom 来源接入时在此合并（registry + mcp + custom），出参结构不变。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.tool import ToolOut
from app.tools import list_tools

router = APIRouter(prefix="/tools", tags=["tools"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", summary="列出可用工具")
async def list_available_tools(
    _user: CurrentUserDep,
) -> ResponseModel[list[ToolOut]]:
    # 内置从 registry 读；未来 + mcp + custom，出参结构不变
    tools = [ToolOut.model_validate(t) for t in list_tools()]
    return success(data=tools)
