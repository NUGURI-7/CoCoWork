"""
    @project: DaisyWind
    @Author: niu
    @file: __init__.py.py
    @date: 2026/4/10 18:07
    @desc:
"""
from fastapi import APIRouter
from backend.app.api.v1.chat.chat import router as crud_router
from backend.app.api.v1.chat.stream import router as stream_router


chat_router = APIRouter()



chat_router.include_router(crud_router)
chat_router.include_router(stream_router)