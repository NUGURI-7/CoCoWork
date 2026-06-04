from uuid import UUID

from app.agents.templates import get_template
from app.core.exceptions import ValidationException, NotFound404
from app.models import User, Agent
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate


class AgentService:
    """Agent CRUD。可见性：用户只能看到自己创建的 Agent。

        AgentOut 无跨实体计算字段，直接 model_validate(ORM 实例) 即可。
    """

    async def create(self, user: User, data: AgentCreate) -> AgentOut:
        # template 存的是内置模板 registry 的 key —— 校验在册
        if get_template(data.template) is None:
            raise ValidationException(f"模板不存在：{data.template}")

        agent = await Agent.create(
            created_by = user,
            name=data.name,
            description=data.description,
            template=data.template,
            config=data.config,
        )
        return AgentOut.model_validate(agent)

    async def list_own(self, user: User) -> list[AgentOut]:
        agents = await Agent.filter(created_by=user).order_by("-created_at")

        return [AgentOut.model_validate(agent) for agent in agents]


    async def get_by_id(self, user:User, agent_id: UUID) -> AgentOut:
        agent = await Agent.filter(created_by=user, id=agent_id).filter()
        if agent is None:
            raise NotFound404("Agent 不存在")
        return AgentOut.model_validate(agent)

    async def update(self, user: User, agent_id: UUID, data: AgentUpdate) -> AgentOut:
        agent = await Agent.filter(created_by=user, id=agent_id).first()
        if agent is None:
            raise NotFound404("Agent 不存在")

        # 只改 name/description/config；template 锁死不动
        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.config is not None:
            agent.config = data.config

        await agent.save()
        return AgentOut.model_validate(agent)

    async def delete(self, user: User, agent_id: UUID) -> None:
        agent = await Agent.filter(created_by=user, id=agent_id).first()
        if agent is None:
            raise NotFound404("Agent 不存在")
        await agent.delete()



async def get_agent_service() -> AgentService:
    return AgentService()






















