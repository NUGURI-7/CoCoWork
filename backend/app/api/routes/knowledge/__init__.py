from fastapi import APIRouter

from app.api.routes.knowledge.knowledge_base import router as knowledge_base_router

router = APIRouter()
router.include_router(knowledge_base_router)

__all__ = ["router"]
