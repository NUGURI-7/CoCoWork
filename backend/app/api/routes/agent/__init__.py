from fastapi import APIRouter

from app.api.routes.agent.agent import router as agent_router

router = APIRouter()
router.include_router(agent_router)

__all__ = ["router"]