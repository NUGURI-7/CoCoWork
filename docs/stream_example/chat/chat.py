"""
    @project: DaisyWind
    @Author: niu
    @file: chat.py.py
    @date: 2026/4/10 18:09
    @desc: Chat 对话 CRUD 路由
"""
from fastapi import APIRouter, Depends

from backend.app.core.depends import get_current_user, get_conversation_or_404
from backend.app.core.response import success
from backend.app.models import User, Conversation
from backend.app.schemas.chat_schema import ConversationOut, MessageOut
from backend.app.services.chat_service import ChatService

router = APIRouter()


@router.get("/conversations")
async def list_conversations(user: User = Depends(get_current_user)):
    """获取当前用户的对话列表。"""
    conversations = await ChatService.list_conversations(user)

    return success(data=[
        ConversationOut.model_validate(con).model_dump() for con in conversations
    ])


@router.get("/conversations/{uuid}")
async def get_conversation(conversation: Conversation = Depends(get_conversation_or_404)):
    """获取对话详情（含消息列表）。"""
    messages = await ChatService.get_chat_messages(conversation)
    data = ConversationOut.model_validate(conversation).model_dump()
    data["messages"] = [
        MessageOut.model_validate(mes).model_dump()
        for mes in messages
    ]

    return success(data=data)

@router.delete("/conversations/{uuid}")
async def del_conversation(conversation: Conversation = Depends(get_conversation_or_404)):
    """删除对话（级联删除消息）。"""
    await conversation.delete()
    return success(message="删除成功")

