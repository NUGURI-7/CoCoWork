"""
    @project: DaisyWind
    @Author: niu
    @file: chat_model.py.py
    @date: 2026/2/12 15:42
    @desc:
"""

from tortoise import fields

from backend.app.db.base import BaseModel, UUIDModel, TimestampMixin


class Conversation(BaseModel, UUIDModel, TimestampMixin):
    """对话/会话"""
    title = fields.CharField(max_length=200, default="New chat")
    model = fields.CharField(max_length=50, default="deepseek-chat")
    provider = fields.CharField(max_length=20, default="deepseek")
    summary = fields.TextField(null=True)

    user = fields.ForeignKeyField(
        "models.User", related_name="conversation", on_delete=fields.CASCADE
    )

    class Meta:
        table = "conversation"
        ordering = ["-updated_at"]
        indexes = [("user_id", "updated_at")]

    def __str__(self):
        return f"Conversation({self.title})"

class ChatMessage(BaseModel, UUIDModel, TimestampMixin):
    """聊天消息"""

    role = fields.CharField(max_length=20)
    content = fields.JSONField()
    token_count = fields.IntField(null=True)
    cost = fields.DecimalField(max_digits=10, decimal_places=6, null=True)

    conversation = fields.ForeignKeyField(
        "models.Conversation", related_name="message", on_delete=fields.CASCADE
    )

    class Meta:
        table = "chat_message"
        ordering = ["created_at"]
        indexes = [("conversation_id", "created_at")]

    def __str__(self):
        return f"Message({self.role}: {self.content[:30]})"