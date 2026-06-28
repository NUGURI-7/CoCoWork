from fastapi import APIRouter

from app.api.routes.mcp.mcp import router as mcp_router

router = APIRouter()
router.include_router(mcp_router)

__all__ = ["router"]
