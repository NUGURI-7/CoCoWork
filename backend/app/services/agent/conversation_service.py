"""单 Agent 会话：员工直接打开一个 Agent 聊天，不经工作空间。

会话与工作空间共用 conversations 表（agent 列有值、workspace 列为空），消息、产物也
共用各自的表。归属一律以 created_by 为准：同一个 Agent，每个人只看得到自己的会话。

「这个 Agent 能不能看 / 能不能用」不在本服务判断 —— 调用方先经 access 模块拿到 Agent，
本服务只管会话这一层。
"""

from uuid import UUID

from tortoise.exceptions import IntegrityError

from app.core.exceptions import AppApiException, NotFound404
from app.models import Agent, Conversation, User
from app.schemas.agent import AgentConfig, AgentConversationOut
from app.schemas.workspace import ConversationUpdate
from app.services.workspace.conversation_service import generate_conversation_title


class AgentConversationService:

    async def _find_owned(
            self, user: User, agent: Agent, conversation_id: UUID,
    ) -> Conversation | None:
        return await Conversation.filter(
            id=conversation_id, agent_id=agent.id, created_by_id=user.id,
        ).first()

    async def get_owned(
            self, user: User, agent: Agent, conversation_id: UUID,
    ) -> Conversation:
        conv = await self._find_owned(user, agent, conversation_id)
        if conv is None:
            raise NotFound404("Conversation 不存在")
        return conv

    async def get_or_create(
            self, user: User, agent: Agent, conversation_id: UUID,
    ) -> Conversation:
        """取该用户在这个 Agent 下的会话；还不存在就用这个 ID 新建。

        会话在用户发出第一句话时才入库，ID 由前端生成。发消息与起名两个请求
        同时到达，都走这里。与工作空间那份（get_or_create_in_workspace）同一套做法。
        """
        conv = await self._find_owned(user, agent, conversation_id)
        if conv is not None:
            return conv

        try:
            await Conversation.create(
                id=conversation_id, created_by_id=user.id, agent_id=agent.id,
            )
        except IntegrityError:
            pass  # 这个 ID 已存在：并发的另一个请求刚建好，或它属于别人。下面统一重查

        return await self.get_owned(user, agent, conversation_id)

    async def list_for_agent(self, user: User, agent: Agent) -> list[AgentConversationOut]:
        """该用户在这个 Agent 下的会话，按 updated_at 倒序（最近活跃在前）。"""
        convs = await Conversation.filter(
            agent_id=agent.id, created_by_id=user.id,
        ).order_by("-updated_at")
        return [AgentConversationOut.model_validate(c) for c in convs]

    async def update(
            self, user: User, agent: Agent, conversation_id: UUID, data: ConversationUpdate,
    ) -> AgentConversationOut:
        conv = await self.get_owned(user, agent, conversation_id)
        if data.title is not None:
            conv.title = data.title
        if data.config is not None:
            conv.config = data.config
        await conv.save()
        return AgentConversationOut.model_validate(conv)

    async def delete(self, user: User, agent: Agent, conversation_id: UUID) -> None:
        """删会话。FK CASCADE 连带删消息与产物记录。"""
        conv = await self.get_owned(user, agent, conversation_id)
        await conv.delete()

    async def generate_title(
            self, user: User, agent: Agent, conversation_id: UUID, content: str,
    ) -> str:
        """用这个 Agent 自己配的对话模型起名。已有标题直接返回，不调模型。"""
        conv = await self.get_or_create(user, agent, conversation_id)
        if conv.title:
            return conv.title

        cfg = AgentConfig.model_validate(agent.config)
        if cfg.models.chat is None:
            raise AppApiException(code=503, message="Agent 还没配对话模型，无法生成标题")
        return await generate_conversation_title(conv.id, cfg.models.chat.id, content)


async def get_agent_conversation_service() -> AgentConversationService:
    return AgentConversationService()
