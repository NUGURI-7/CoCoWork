from uuid import UUID

from app.core.exceptions import NotFound404
from app.models import Conversation, User, Workspace
from app.schemas.workspace import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
)

class ConversationService:
    """Conversation CRUD。

    URL nested 在 /workspaces/{wid}/conversations/*;
    可见性:用户只能访问自己 workspace 下的 conversation。
    归属校验靠 ORM JOIN 一次过(conversation→workspace→user)。
    """

    async def _ensure_workspace_owned(self, user: User, workspace_id: UUID) -> None:
        """校验 workspace 归属 user(不存在 / 不归属一律返 404)。"""
        exists = await Workspace.filter(id=workspace_id, created_by=user).exists()
        if not exists:
            raise NotFound404("Workspace 不存在")

    async def _get_user_conversation(
        self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> Conversation:
        """一次 JOIN 取 conversation + 归属校验。"""
        conv =  await Conversation.filter(
            id=conversation_id,
            workspace_id=workspace_id,
            workspace__created_by=user,
        ).first()
        if conv is None:
            raise NotFound404("Conversation 不存在")
        return conv

    async def create(
        self, user: User, workspace_id: UUID, data: ConversationCreate,
    ) -> ConversationOut:
        """创建对话。先校验 workspace 归属再挂。"""
        await self._ensure_workspace_owned(user, workspace_id)
        conv = await Conversation.create(
            workspace_id=workspace_id,
            title=data.title,
        )
        return ConversationOut.model_validate(conv)

    async def list_in_workspace(
            self, user: User, workspace_id: UUID,
    ) -> list[ConversationOut]:
        """列 workspace 下的对话,按 updated_at 倒序(最近活跃在前)。"""
        await self._ensure_workspace_owned(user, workspace_id)
        convs = await Conversation.filter(workspace_id=workspace_id).order_by("-updated_at")
        return [ConversationOut.model_validate(c) for c in convs]

    async def get_by_id(
            self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> ConversationOut:
        conv = await self._get_user_conversation(user, workspace_id, conversation_id)
        return ConversationOut.model_validate(conv)

    async def update(
            self, user: User, workspace_id: UUID, conversation_id: UUID,
            data: ConversationUpdate,
    ) -> ConversationOut:
        conv = await self._get_user_conversation(user, workspace_id, conversation_id)
        if data.title is not None:
            conv.title = data.title
        if data.config is not None:
            conv.config = data.config
        await conv.save()
        return ConversationOut.model_validate(conv)

    async def delete(
            self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> None:
        """删 conversation。FK CASCADE 自动连带删 messages。"""
        conv = await self._get_user_conversation(user, workspace_id, conversation_id)
        await conv.delete()


async def get_conversation_service() -> ConversationService:
    return ConversationService()






