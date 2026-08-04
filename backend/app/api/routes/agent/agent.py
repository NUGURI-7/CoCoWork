from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends

from app.agents.templates import list_templates
from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate, TemplateOut
from app.services.agent import AgentService, get_agent_service

router = APIRouter(prefix="/agents", tags=["agents"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]
AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


@router.post("", summary="创建 Agent")
async def create_agent(
        data: AgentCreate,
        current_user: CurrentUserDep,
        svc: AgentServiceDep
) -> ResponseModel[AgentOut]:
    agent = await svc.create(current_user, data)
    return success(data=agent, message="创建成功")


@router.get("", summary="列出自己的 Agent")
async def list_agents(
        current_user: CurrentUserDep,
        svc: AgentServiceDep
) -> ResponseModel[list[AgentOut]]:
    agents = await svc.list_own(current_user)
    return success(data=agents)


@router.get("/templates", summary="列出内置模板")
async def list_agent_templates(
        current_user: CurrentUserDep,
) -> ResponseModel[list[TemplateOut]]:
    """模板池 = 进程内注册表，与用户无关；登录态只用来挡未认证访问。

    不经 service：这里没有业务逻辑可装（不查库、不分用户、无权限差异），
    转一层只会得到一个一行的空壳。

    **必须注册在 /{agent_id} 之前** —— FastAPI 按注册顺序匹配，否则
    "templates" 会被当成 agent_id 拿去转 UUID，直接 422。
    """
    return success(data=[TemplateOut.model_validate(t) for t in list_templates()])


@router.get("/{agent_id}", summary="Agent 详情")
async def get_agent(
        agent_id: UUID,
        current_user: CurrentUserDep,
        svc: AgentServiceDep
) -> ResponseModel[AgentOut]:
    agent = await svc.get_by_id(current_user, agent_id)
    return success(data=agent)


@router.put("/{agent_id}", summary="更新 Agent")
async def update_agent(
        agent_id: UUID,
        data: AgentUpdate,
        current_user: CurrentUserDep,
        svc: AgentServiceDep
) -> ResponseModel[AgentOut]:
    agent = await svc.update(current_user, agent_id, data)
    return success(data=agent, message="更新成功")


@router.delete("/{agent_id}", summary="删除 Agent")
async def delete_agent(
        agent_id: UUID,
        current_user: CurrentUserDep,
        svc: AgentServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, agent_id)
    return success(message="删除成功")
