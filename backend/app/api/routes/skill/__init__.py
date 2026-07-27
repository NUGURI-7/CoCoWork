from fastapi import APIRouter

from app.api.routes.skill.skill import router as skill_router

router = APIRouter()
router.include_router(skill_router)

__all__ = ["router"]