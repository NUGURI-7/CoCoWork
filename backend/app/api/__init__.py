from fastapi import APIRouter

api_router = APIRouter()

# D1 阶段挂载 user 路由，示例：
# from app.api.routes import user
# api_router.include_router(user.router, prefix="/users", tags=["users"])
