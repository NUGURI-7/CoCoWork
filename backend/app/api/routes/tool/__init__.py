from fastapi import APIRouter

from app.api.routes.tool.tool import router as tool_router

router = APIRouter()
router.include_router(tool_router)

__all__ = ["router"]
