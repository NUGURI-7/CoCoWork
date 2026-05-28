from fastapi import APIRouter

from app.api.routes.knowledge.document import router as document_router
from app.api.routes.knowledge.knowledge_base import router as knowledge_base_router

router = APIRouter()
router.include_router(knowledge_base_router)
router.include_router(document_router)

__all__ = ["router"]
