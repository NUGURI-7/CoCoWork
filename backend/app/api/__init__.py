from fastapi import APIRouter

from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.model import router as model_router
from app.api.routes.user import router as user_router
from app.api.routes.agent import router as agent_router   # ← 加这行


api_router = APIRouter()
api_router.include_router(user_router)
api_router.include_router(model_router)
api_router.include_router(knowledge_router)
api_router.include_router(agent_router)
