from uuid import UUID

from tortoise.exceptions import IntegrityError

from app.core.exceptions import Conflict409, NotFound404
from app.models import Agent, User, Workspace, WorkspaceMember
from app.schemas.workspace import MemberOut, MemberRecruitIn


class MemberService:
    """Workspace 成员（招募进来的 agent 引用）CRUD。

    URL nested 在 /workspaces/{wid}/members/*；用户只能管理自己 workspace 下的成员。
    成员是对 agents 表的不可变引用，workspace 侧不可改（要变去 agent 那侧变），
    故只开招募 / 列表 / 踢人，不开 Update。
    """

    async def _ensure_workspace_owned(self, user: User, workspace_id: UUID) -> None:
        """校验 workspace 归属 user（不存在 / 不归属一律 404）。"""
        exists = await Workspace.filter(id=workspace_id, created_by=user).exists()
        if not exists:
            raise NotFound404("Workspace 不存在")

    async def recruit(
            self, user: User, workspace_id: UUID, data: MemberRecruitIn,
    ) -> MemberOut:
        """招募一个现成 agent 进 workspace。

        双重归属校验：workspace 与 agent 都得归 user。
        unique(workspace, agent) 撞库 → 409（已招募过同一 agent）：以 DB 约束为准
        （race-safe），不做预查。
        """

        await self._ensure_workspace_owned(user, workspace_id)

        agent = await Agent.filter(id=data.agent_id, created_by=user).first()
        if agent is None:
            raise NotFound404("Agent 不存在")

        try:
            member = await WorkspaceMember.create(
                workspace_id=workspace_id,
                agent=agent
            )
        except IntegrityError as exc:
            raise Conflict409("该 Agent 已招募进此 workspace") from exc

        # agent 是上面取出的实例，member.agent 命中缓存，MemberOut 内嵌摘要零额外查询
        return MemberOut.model_validate(member)

    async def list_in_workspace(
            self, user: User, workspace_id: UUID,
    ) -> list[MemberOut]:
        """列 workspace 下的成员，按招募时间正序（先来的在前）。"""
        await self._ensure_workspace_owned(user, workspace_id)
        members = await (
            WorkspaceMember.filter(workspace_id=workspace_id)
            .prefetch_related("agent")
            .order_by("created_at")
        )
        return [MemberOut.model_validate(m) for m in members]

    async def remove(
            self, user: User, workspace_id: UUID, member_id: UUID,
    ) -> None:
        """踢人。一次 JOIN 取成员 + 归属校验（member→workspace→user）。"""
        member = await WorkspaceMember.filter(
            id=member_id,
            workspace_id=workspace_id,
            workspace__created_by=user
        ).first()
        if member is None:
            raise NotFound404("成员不存在")
        await member.delete()

async def get_member_service() -> MemberService:
    return MemberService()






