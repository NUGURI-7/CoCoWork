"""Workspace 产出物列表端点。

GET /workspaces/{wid}/artifacts  →  这个 workspace 下的全部沙箱产物

**跨对话**：产物绑 workspace 不绑对话（设计稿决策 14），所以在对话 A 里也能
翻到对话 B 的产出。每项带 conversation_name，面板据此分组。

不走 service 层：一条带归属条件的查询，没有业务逻辑可言 ——
与 routes/sandbox/artifact.py 的既有姿势一致。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.sandbox import SandboxArtifact
from app.models.user import User
from app.schemas.sandbox import WorkspaceArtifactItem

router = APIRouter(prefix="/workspaces/{workspace_id}/artifacts", tags=["artifacts"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


@router.get("", summary="列出 workspace 下的沙箱产物")
async def list_workspace_artifacts(
        workspace_id: UUID,
        current_user: CurrentUserDep,
        limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
        offset: Annotated[int, Query(ge=0)] = 0,
) -> ResponseModel[list[WorkspaceArtifactItem]]:
    """按产出时间倒序（新的在上）。

    归属校验走 JOIN 一次过：产物 → 对话 → workspace → 当前用户。条件进 WHERE，
    就不存在「查到了但忘了判权限」这个中间状态。

    offset 分页：产物是低频写入的，翻页时新数据插到前面导致错位的窗口极小，
    不值得为它上游标分页。
    """
    artifacts = (
        await SandboxArtifact.filter(
            conversation__workspace_id=workspace_id,
            conversation__workspace__created_by=current_user,
        )
        .select_related("conversation")
        .order_by("-created_at")
        .limit(limit)
        .offset(offset)
    )

    return success(
        data=[
            WorkspaceArtifactItem(
                id=a.id,
                filename=a.filename,
                size=a.size,
                content_type=a.content_type,
                conversation_id=a.conversation_id,
                conversation_name=a.conversation.title,
                message_id=a.message_id,
                created_at=a.created_at,
            )
            for a in artifacts
        ]
    )

