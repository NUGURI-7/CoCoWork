"""单 Agent 会话的请求 / 响应 schema。

URL nested 在 /agents/{agent_id}/conversations/* 下，agent_id 走 path。
改名、起名沿用工作空间那几个 schema（ConversationUpdate / ConversationTitleIn / ConversationTitleOut），
两种会话在这几件事上的契约完全一样。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent.chat_schema import TextBlock


class AgentConversationOut(BaseModel):
    """单 Agent 会话对外输出。"""

    id: UUID
    agent_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentConversationStreamIn(BaseModel):
    """单 Agent 会话发消息的请求体：只送当前这一句，历史由后端从库里拼。

    只收文本块：拖入历史产物（决策 25）目前只在工作空间里支持。
    """

    content: list[TextBlock] = Field(..., min_length=1)
