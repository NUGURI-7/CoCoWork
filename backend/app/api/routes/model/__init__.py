from fastapi import APIRouter

from app.api.routes.model.ai_model import (
    flat_router as ai_model_flat_router,
    nested_router as ai_model_nested_router,
)
from app.api.routes.model.catalog import router as catalog_router
from app.api.routes.model.provider import router as provider_router

router = APIRouter()
router.include_router(provider_router)
router.include_router(ai_model_nested_router)
router.include_router(ai_model_flat_router)
router.include_router(catalog_router)

__all__ = ["router"]
