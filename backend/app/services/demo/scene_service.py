"""官网体验场景：把场景名解析成当前用户该去的页面，工作空间按模板给用户复制一份。"""

from uuid import UUID

from tortoise.transactions import in_transaction

from app.core.config import settings
from app.core.exceptions import NotFound404
from app.models import User, Workspace, WorkspaceMember
from app.schemas.demo import SceneEntryOut
from app.services.agent.access import get_usable_agent


async def resolve_scene(user: User, scene: str) -> SceneEntryOut:
    spec = settings.DEMO_SCENES.get(scene)
    if spec is None:
        raise NotFound404("体验场景不存在")
    if spec.kind == "agent":
        await get_usable_agent(user, spec.target_id)
        return SceneEntryOut(kind="agent", target_id=spec.target_id)
    workspace = await ensure_workspace_copy(user, spec.target_id)
    return SceneEntryOut(kind="workspace", target_id=workspace.id)


async def ensure_workspace_copy(user: User, template_id: UUID) -> Workspace:
    owned = await Workspace.filter(id=template_id, created_by=user).first()
    if owned is not None:
        return owned

    async with in_transaction() as conn:
        template = (
            await Workspace.filter(id=template_id).select_for_update().using_db(conn).first()
        )
        if template is None:
            raise NotFound404("体验场景不存在")

        existing = (
            await Workspace.filter(created_by=user, cloned_from_id=template_id)
            .using_db(conn)
            .first()
        )
        if existing is not None:
            return existing

        copy = await Workspace.create(
            created_by=user,
            name=template.name,
            description=template.description,
            avatar_url=template.avatar_url,
            supervisor=template.supervisor,
            config=template.config,
            cloned_from=template,
            using_db=conn,
        )
        members = await WorkspaceMember.filter(workspace_id=template.id).using_db(conn)
        await WorkspaceMember.bulk_create(
            [
                WorkspaceMember(workspace=copy, agent_id=m.agent_id, config=m.config)
                for m in members
            ],
            using_db=conn,
        )
    return copy
