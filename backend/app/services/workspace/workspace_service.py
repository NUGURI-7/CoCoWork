from uuid import UUID

from app.core.exceptions import NotFound404
from app.models import User, Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate


class WorkspaceService:
    """Workspace CRUD。可见性:用户只能看到自己创建的 Workspace。

    WorkspaceOut 无跨实体计算字段,直接 model_validate(ORM 实例) 即可。
    """

    async def create(self, user: User, data: WorkspaceCreate) -> WorkspaceOut:
        """创建 workspace。

        supervisor / config 走 model 层 default=dict,创建时不显式传。
        将来对齐 AgentConfig 后,可在此填充默认 SupervisorConfig(默认模型 + 默认 prompt)。
        """
        workspace = await Workspace.create(
            created_by=user,
            name=data.name,
            description=data.description,
            avatar_url=data.avatar_url,
        )
        return WorkspaceOut.model_validate(workspace)

    async def list_own(self, user: User) -> list[WorkspaceOut]:
        """列当前用户的所有 workspace,按创建时间倒序。"""
        workspaces = await Workspace.filter(created_by=user).order_by("-created_at")
        return [WorkspaceOut.model_validate(ws) for ws in workspaces]

    async def get_by_id(self, user: User, workspace_id: UUID) -> WorkspaceOut:
        """按 id 取 workspace,归属校验。"""
        workspace = await Workspace.filter(created_by=user, id=workspace_id).first()
        if workspace is None:
            raise NotFound404("Workspace 不存在")
        return WorkspaceOut.model_validate(workspace)

    async def update(
        self, user: User, workspace_id: UUID, data: WorkspaceUpdate,
    ) -> WorkspaceOut:
        """PATCH 风格部分更新:只动传过来的字段。"""
        workspace = await Workspace.filter(created_by=user, id=workspace_id).first()
        if workspace is None:
            raise NotFound404("Workspace 不存在")

        if data.name is not None:
            workspace.name = data.name
        if data.description is not None:
            workspace.description = data.description
        if data.avatar_url is not None:
            workspace.avatar_url = data.avatar_url
        if data.supervisor is not None:
            workspace.supervisor = data.supervisor
        if data.config is not None:
            workspace.config = data.config

        await workspace.save()
        return WorkspaceOut.model_validate(workspace)

    async def delete(self, user: User, workspace_id: UUID) -> None:
        """删 workspace。FK CASCADE 自动连带删 members/conversations/messages。"""
        workspace = await Workspace.filter(created_by=user, id=workspace_id).first()
        if workspace is None:
            raise NotFound404("Workspace 不存在")
        await workspace.delete()


async def get_workspace_service() -> WorkspaceService:
    return WorkspaceService()