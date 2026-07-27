from fastapi import APIRouter

from app.api.routes.workspace.conversation import router as conversation_router
from app.api.routes.workspace.message import router as message_router
from app.api.routes.workspace.stream import router as stream_router
from app.api.routes.workspace.workspace import router as workspace_router
from app.api.routes.workspace.member import router as member_router
from app.api.routes.workspace.artifact import router as artifact_router


router = APIRouter()
router.include_router(workspace_router)
router.include_router(conversation_router)
router.include_router(message_router)
router.include_router(stream_router)
router.include_router(member_router)
router.include_router(artifact_router)

__all__ = ["router"]